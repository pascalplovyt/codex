"""Entry point - restore a portable backup archive onto a new machine.

Usage:
    py -3 restore.py --list
    py -3 restore.py --install latest
    py -3 restore.py --install 20260421T103000
    py -3 restore.py --install-file path\\to\\system_20260421T103000.tar.gz
    py -3 restore.py --install latest --drop     # DROP existing DB first
    py -3 restore.py --install-file path\\to\\archive.tar.gz --dry-run

High-level flow:

    1. Load config.
    2. Pick an archive (from --install-file or from the remote listing).
    3. Download it (skip if --install-file already local).
    4. Extract to staging/restore_<ts>/ and verify sha256 hashes.
    5. Restore the database using either:
       * the physical snapshot for fast same-version recovery, or
       * pg_restore of the logical dump for portable recovery.
    6. Materialise the app/ files into <source_root>/ (after taking a
       safety snapshot of the current source_root to
       staging/preinstall_<ts>.zip).
    7. Decrypt env.enc -> <env_file>  (using secrets/env_key.bin).
    8. Print a summary with next-step suggestions.

Before anything destructive, restore.py pauses and asks for
"RESTORE" to be typed, unless --yes is passed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import archive as ar
from lib import config as cfgmod
from lib import crypto
from lib import manifest as mf
from lib import pg
from lib import remote as rmod


_ARCHIVE_RE = re.compile(r"^(?P<system>[A-Za-z0-9_.\-]+)_"
                         r"(?P<ts>\d{8}T\d{6})\.tar\.gz$")


def _list_remote(cfg: dict) -> list:
    remote = rmod.get_remote(cfg)
    names = remote.list()
    out = []
    for n in names:
        m = _ARCHIVE_RE.match(n)
        if not m:
            continue
        if m.group("system") != cfg.get("system_name"):
            continue
        out.append((m.group("ts"), n))
    out.sort(reverse=True)
    return out


def _pick_archive(cfg: dict, selector: str) -> str:
    items = _list_remote(cfg)
    if not items:
        raise RuntimeError("no archives found on remote for system "
                           f"{cfg.get('system_name')!r}")
    if selector in ("latest", "", None):
        return items[0][1]
    # Accept either the full filename, or just the timestamp.
    for ts, name in items:
        if selector == name or selector == ts:
            return name
    raise RuntimeError(f"archive {selector!r} not found on remote")


def _snapshot_path(label: str, src: Path, staging: Path, ts: str, say) -> Path | None:
    """Zip whatever currently lives at *src* before we write over it.
    Returns the produced .zip path, or None if src didn't exist."""
    if not src.exists():
        return None
    out_dir = staging / f"preinstall_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{label}.zip"
    say(f"safety snapshot: {src} -> {out}")
    with zipfile.ZipFile(str(out), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if src.is_file():
            try:
                zf.write(str(src), arcname=src.name)
            except Exception:
                pass
            return out
        for p in sorted(src.rglob("*")):
            try:
                if p.is_file():
                    rel = p.relative_to(src)
                    # Skip the backup tool's own scratch folders to avoid
                    # recursive / huge zips.
                    if rel.parts and rel.parts[0] in (
                        "pg_portable_backup", "staging", "logs"):
                        continue
                    zf.write(str(p), arcname=rel.as_posix())
            except Exception:
                continue
    return out


def _confirm(prompt: str, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    try:
        val = input(prompt)
    except EOFError:
        return False
    return val.strip() == "RESTORE"


def run(cfg: dict, archive_file: Path | None, selector: str,
        drop: bool, skip_app: bool, skip_env: bool,
        auto_yes: bool, restore_mode: str, dry_run: bool) -> int:

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    staging = Path(cfg["staging_dir"])
    logs_dir = Path(cfg["logs_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"restore_{ts}.log"

    with open(log_path, "w", encoding="utf-8") as log:
        def say(msg):
            line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()

        try:
            say(f"=== restore start - system={cfg.get('system_name')} ts={ts}")

            # 2. pick archive
            if archive_file:
                archive_path = Path(archive_file)
                if not archive_path.exists():
                    raise FileNotFoundError(archive_path)
                say(f"using local archive: {archive_path}")
            else:
                name = _pick_archive(cfg, selector)
                remote = rmod.get_remote(cfg)
                say(f"downloading from remote: {name}")
                archive_path = remote.download(name, staging, log_fp=log)

            # 4. extract + verify
            work = staging / f"restore_{ts}"
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True, exist_ok=True)
            say(f"extracting to {work}")
            ar.extract_archive(archive_path, work)

            manifest_path = work / "manifest.json"
            if not manifest_path.exists():
                raise RuntimeError("archive has no manifest.json - refusing to continue")
            manifest = mf.read(manifest_path)
            say(f"archive system={manifest.get('system_name')} "
                f"created={manifest.get('created_utc')} "
                f"pg={manifest.get('postgres_server','?')[:60]}")
            problems = mf.verify(manifest, work)
            if problems:
                raise RuntimeError("manifest verification failed:\n" +
                                   "\n".join(problems))
            say("manifest verified OK")

            available_modes = manifest.get("recovery_modes") or ["portable"]
            has_fast_snapshot = (work / "physical" / "data" / "PG_VERSION").exists()
            cluster_cfg = cfg.get("local_cluster") or {}
            if restore_mode == "fast":
                if not has_fast_snapshot:
                    raise RuntimeError("archive does not contain a fast recovery snapshot")
                if not cluster_cfg.get("data_dir"):
                    raise RuntimeError("config has no local_cluster.data_dir for fast restore")
                selected_mode = "fast"
            elif restore_mode == "portable":
                selected_mode = "portable"
            else:
                selected_mode = (
                    "fast"
                    if has_fast_snapshot and cluster_cfg.get("data_dir")
                    else "portable"
                )
            say(f"restore mode: {selected_mode} (available: {', '.join(available_modes)})")

            app_stage = work / "app"
            env_enc = work / "config" / "env.enc"
            planned_targets = []
            if app_stage.exists():
                src_map = {}
                smap_path = app_stage / "_sources.json"
                if smap_path.exists():
                    try:
                        src_map = json.loads(smap_path.read_text(encoding="utf-8"))
                    except Exception as e:
                        say(f"  warning: could not parse _sources.json: {e}")
                src_root_fb = Path(cfg.get("source_root") or "")
                for entry in sorted(app_stage.iterdir()):
                    if entry.name == "_sources.json":
                        continue
                    label = entry.name
                    rec = src_map.get(label) or {}
                    dst_str = rec.get("original_path")
                    if dst_str:
                        dst = Path(dst_str)
                    elif str(src_root_fb):
                        dst = src_root_fb / label
                    else:
                        dst = None
                    planned_targets.append({
                        "label": label,
                        "source": str(entry),
                        "target": str(dst) if dst else "(no target configured)",
                    })

            if dry_run:
                say("DRY-RUN: verified archive and planned restore actions only.")
                say(f"DRY-RUN: database restore mode would be '{selected_mode}'.")
                if selected_mode == "fast":
                    say(f"DRY-RUN: would replace cluster data_dir {cluster_cfg.get('data_dir')}.")
                else:
                    say(f"DRY-RUN: would restore logical dump into database {cfg['postgres']['database']}.")
                if planned_targets:
                    say("DRY-RUN: app targets:")
                    for item in planned_targets:
                        say(f"  - {item['label']} -> {item['target']}")
                else:
                    say("DRY-RUN: no app payload found in archive.")
                if env_enc.exists() and cfg.get("env_file"):
                    say(f"DRY-RUN: would decrypt env/config into {cfg.get('env_file')}.")
                elif cfg.get("env_file"):
                    say("DRY-RUN: archive has no encrypted env/config payload.")
                say("=== DRY-RUN OK ===")
                return 0

            # prompt
            if not _confirm(
                "\n*** About to restore the database and overwrite app files. ***\n"
                "Type RESTORE to continue, anything else aborts: ",
                auto_yes):
                say("aborted by operator")
                return 3

            # 5. restore database
            if selected_mode == "fast":
                snapshot_dir = work / "physical" / "data"
                current_cluster = Path(cluster_cfg["data_dir"])
                _snapshot_path("cluster_data", current_cluster, staging, ts, say)
                was_running = pg.cluster_is_running(cfg["postgres"], cluster_cfg, log)
                if was_running:
                    say("stopping local PostgreSQL cluster ...")
                    pg.stop_cluster(cfg["postgres"], cluster_cfg, log)
                say(f"restoring physical cluster snapshot -> {current_cluster}")
                pg.restore_cluster_data(cluster_cfg, snapshot_dir, log)
                say("starting restored local PostgreSQL cluster ...")
                pg.start_cluster(cfg["postgres"], cluster_cfg, log)
                if not pg.wait_for_port(cfg["postgres"], timeout_sec=30):
                    raise RuntimeError("restored PostgreSQL cluster did not come online")
            else:
                dump = work / "database" / "cluster.dump"
                globals_sql = work / "database" / "globals.sql"
                if not dump.exists():
                    raise RuntimeError("no database/cluster.dump in archive")

                if globals_sql.exists():
                    say("applying globals.sql ...")
                    pg.run_globals_sql(cfg["postgres"], globals_sql, log_fp=log)

                say(f"pg_restore -> database {cfg['postgres']['database']} "
                    f"(drop_first={drop})")
                pg.restore_database(cfg["postgres"], dump,
                                    cfg["postgres"]["database"],
                                    log_fp=log, drop_first=drop)

            # 6. source tree(s)
            if not skip_app:
                if not app_stage.exists():
                    say("app/ not present in archive - nothing to install")
                else:
                    # _sources.json maps <label> -> {original_path, is_directory}
                    # so we can put each source back where it came from. Archives
                    # created before this feature won't have it - in that case
                    # we fall back to installing each label under source_root.
                    for item in planned_targets:
                        label = item["label"]
                        entry = app_stage / label
                        dst_str = item["target"]
                        if not dst_str or dst_str == "(no target configured)":
                            say(f"  SKIP {label}: no target (missing "
                                f"_sources.json and source_root)")
                            continue
                        dst = Path(dst_str)

                        _snapshot_path(label, dst, staging, ts, say)

                        say(f"installing: {label}  ->  {dst}")
                        try:
                            if entry.is_dir():
                                if dst.exists():
                                    if dst.is_dir():
                                        shutil.rmtree(dst)
                                    else:
                                        dst.unlink()
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copytree(str(entry), str(dst))
                            else:
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(str(entry), str(dst))
                        except Exception as e:
                            say(f"  ERROR installing {label}: {e}")
                            raise
            else:
                say("skipping app files (--skip-app)")

            # 7. env
            if not skip_env:
                env_dst_str = cfg.get("env_file")
                if env_enc.exists() and env_dst_str:
                    env_dst = Path(env_dst_str)
                    key_path = Path(cfg["secrets_dir"]) / "env_key.bin"
                    if not key_path.exists():
                        say(f"WARNING: env key missing at {key_path} - "
                            ".env NOT decrypted. Copy env_key.bin from the "
                            "source machine and re-run restore.py --skip-app")
                    else:
                        key = crypto.ensure_key(key_path)
                        say(f"decrypting env -> {env_dst}")
                        env_dst.parent.mkdir(parents=True, exist_ok=True)
                        crypto.decrypt_file(env_enc, env_dst, key)
            else:
                say("skipping env (--skip-env)")

            say("=== DONE OK ===")
            say("Next: start your application, confirm it connects, and "
                "spot-check a few tables.")
            return 0

        except Exception as e:
            say(f"ERROR: {e}")
            log.write(traceback.format_exc())
            log.flush()
            return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore a portable PG + app backup.")
    ap.add_argument("--config", help="Path to config JSON (default: "
                    "config.<system>.json next to this script)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--install", help="Install this archive. 'latest' picks "
                   "the newest from the remote; or pass a YYYYMMDDTHHMMSS "
                   "timestamp or full filename.")
    g.add_argument("--install-file", help="Use a local .tar.gz instead of "
                   "downloading from the remote.")
    ap.add_argument("--list", action="store_true",
                    help="Just list remote archives and exit.")
    ap.add_argument("--drop", action="store_true",
                    help="DROP the target database first if it exists.")
    ap.add_argument("--restore-mode", choices=["auto", "fast", "portable"],
                    default="auto",
                    help="Choose fast physical restore, portable logical "
                    "restore, or auto-select based on archive contents.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Verify and preview the restore without changing "
                    "the database, app files, or env/config.")
    ap.add_argument("--skip-app", action="store_true",
                    help="Do not overwrite source_root app files.")
    ap.add_argument("--skip-env", action="store_true",
                    help="Do not decrypt env.")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="Skip the typed RESTORE confirmation.")
    args = ap.parse_args()

    if args.config:
        cfg_path = Path(args.config)
    else:
        found = cfgmod.find_default_config()
        if not found:
            print("No config file found. Pass --config <file>", file=sys.stderr)
            return 2
        cfg_path = found

    print(f"using config: {cfg_path}")
    cfg = cfgmod.load(cfg_path)

    if args.list:
        items = _list_remote(cfg)
        if not items:
            print("(no archives found)")
        else:
            print("timestamp          filename")
            print("-----------------  --------------------------------------------")
            for ts, name in items:
                print(f"{ts}  {name}")
        return 0

    if not args.install and not args.install_file:
        print("Pass either --install <ts|latest> or --install-file <path>, "
              "or --list to see what's on the remote.", file=sys.stderr)
        return 2

    return run(
        cfg,
        archive_file=Path(args.install_file) if args.install_file else None,
        selector=args.install or "latest",
        drop=args.drop,
        skip_app=args.skip_app,
        skip_env=args.skip_env,
        auto_yes=args.yes,
        restore_mode=args.restore_mode,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
