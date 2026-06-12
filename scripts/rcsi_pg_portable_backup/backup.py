"""Entry point - create a full portable backup and push it to GDrive.

Usage (Windows):
    py -3 backup.py                      # uses the default config
    py -3 backup.py --config config.rcsi.json
    py -3 backup.py --dry-run            # build locally but skip upload

What it does, step by step:

    1. Load config.
    2. Pick a timestamp and reset staging/
    3. Start the local PG cluster if local_cluster is configured and down.
    4. pg_dump -Fc  ->  staging/database/cluster.dump
    5. pg_dumpall --globals-only -> staging/database/globals.sql (optional)
    6. Optionally stop the local PG cluster and snapshot its data directory
       for fast same-version recovery, then restart it.
    7. Copy each configured source tree into staging/ (with excludes),
       record origin paths in app/_sources.json.
    8. Encrypt the .env file using secrets/env_key.bin (auto-create key
       if missing) and write it to staging/config/env.enc.
    9. Build manifest.json (hashes) and drop it into staging/
   10. Create staging archive staging/<system>_<ts>.tar.gz
   11. Upload to Google Drive (desktop copy or rclone).
   12. Prune old archives on the remote to retention_weeks.
   13. Log everything to logs/backup_<ts>.log; return exit 0/1.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import archive as ar
from lib import config as cfgmod
from lib import crypto
from lib import manifest as mf
from lib import pg
from lib import remote as rmod


def _reset_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def _resolve_source_path(src_root: Path, source_path: str) -> Path:
    p = Path(source_path)
    if p.is_absolute():
        return p
    return (src_root / p) if str(src_root) else p


def _copy_source(src_root: Path, source: dict, stage_app: Path) -> Path:
    src = _resolve_source_path(src_root, source["path"])
    if not src.exists():
        raise FileNotFoundError(f"source not found: {src}")
    dst = stage_app / source["label"]
    excludes = source.get("exclude", [])

    def ignore(dirname, names):
        import fnmatch
        out = []
        for n in names:
            for pat in excludes:
                if fnmatch.fnmatch(n, pat):
                    out.append(n)
                    break
        return out

    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
    else:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(str(src), str(dst), ignore=ignore)

    return src.resolve()


def run(cfg: dict, dry_run: bool = False) -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    system_name = cfg.get("system_name", "system")
    staging = Path(cfg["staging_dir"])
    logs_dir = Path(cfg["logs_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"backup_{ts}.log"

    with open(log_path, "w", encoding="utf-8") as log:
        def say(msg):
            line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()

        try:
            say(f"=== pg_portable_backup start - system={system_name} ts={ts}")

            work = staging / f"build_{ts}"
            _reset_dir(work)
            say(f"staging: {work}")

            cluster_cfg = cfg.get("local_cluster") or {}
            if cluster_cfg.get("data_dir") and not pg.cluster_is_running(cfg["postgres"], cluster_cfg, log):
                say("preflight: starting local PostgreSQL cluster ...")
                pg.start_cluster(cfg["postgres"], cluster_cfg, log)
                if not pg.wait_for_port(cfg["postgres"], timeout_sec=60):
                    raise RuntimeError("local PostgreSQL did not start listening before backup")

            pg_cfg = cfg["postgres"]
            dump_path = work / "database" / "cluster.dump"
            say("step 1/8: pg_dump -Fc ...")
            pg.dump_database(pg_cfg, dump_path, log_fp=log)

            if pg_cfg.get("include_globals", True):
                globals_path = work / "database" / "globals.sql"
                say("step 2/8: pg_dumpall --globals-only ...")
                pg.dump_globals(pg_cfg, globals_path, log_fp=log)

            pg_version = pg.server_version(pg_cfg, log_fp=log)
            say(f"postgres version: {pg_version}")

            recovery_modes = ["portable"]
            cluster_was_running = False
            if cluster_cfg.get("data_dir"):
                say("step 3/8: capturing fast-recovery cluster snapshot ...")
                cluster_stage = work / "physical" / "data"
                cluster_was_running = pg.cluster_is_running(pg_cfg, cluster_cfg, log)
                if cluster_was_running:
                    say("  stopping local PostgreSQL cluster for a clean snapshot ...")
                    pg.stop_cluster(pg_cfg, cluster_cfg, log)
                try:
                    pg.copy_cluster_data(cluster_cfg, cluster_stage, log)
                    meta = {
                        "data_dir": cluster_cfg.get("data_dir"),
                        "port": pg_cfg.get("port"),
                        "postgres_bin_dir": pg_cfg.get("bin_dir"),
                        "postgres_server": pg_version,
                    }
                    (work / "physical").mkdir(parents=True, exist_ok=True)
                    (work / "physical" / "metadata.json").write_text(
                        json.dumps(meta, indent=2),
                        encoding="utf-8",
                    )
                    recovery_modes.append("fast")
                finally:
                    if cluster_was_running:
                        say("  restarting local PostgreSQL cluster ...")
                        pg.start_cluster(pg_cfg, cluster_cfg, log)
                        if not pg.wait_for_port(pg_cfg, timeout_sec=60):
                            raise RuntimeError("local PostgreSQL did not come back after snapshot")

            say("step 4/8: copying source trees ...")
            src_root = Path(cfg.get("source_root") or "")
            app_stage = work / "app"
            app_stage.mkdir(parents=True, exist_ok=True)
            sources_map = {}
            for s in cfg.get("sources", []):
                say(f"  - {s['label']}: {s['path']}")
                used = _copy_source(src_root, s, app_stage)
                sources_map[s["label"]] = {
                    "original_path": str(used),
                    "is_directory": used.is_dir(),
                }
            (app_stage / "_sources.json").write_text(
                json.dumps(sources_map, indent=2), encoding="utf-8"
            )

            env_path_str = cfg.get("env_file")
            if env_path_str:
                env_path = Path(env_path_str)
                if env_path.exists():
                    say("step 5/8: encrypting .env ...")
                    key = crypto.ensure_key(Path(cfg["secrets_dir"]) / "env_key.bin")
                    (work / "config").mkdir(parents=True, exist_ok=True)
                    crypto.encrypt_file(env_path, work / "config" / "env.enc", key)
                else:
                    say(f"  env_file not found ({env_path}) - skipping")

            (work / "RESTORE.md").write_text(_restore_md(system_name, ts), encoding="utf-8")

            say("step 6/8: building manifest ...")
            manifest = mf.build(
                work,
                cfg,
                pg_version,
                extra={
                    "archive_name": f"{system_name}_{ts}.tar.gz",
                    "recovery_modes": recovery_modes,
                },
            )
            mf.write(manifest, work / "manifest.json")

            say("step 7/8: creating tar.gz ...")
            archive_name = f"{system_name}_{ts}.tar.gz"
            archive_path = staging / archive_name
            entries = []
            for p in sorted(work.rglob("*")):
                if p.is_file():
                    entries.append({
                        "src": p,
                        "arcroot": p.relative_to(work).as_posix(),
                        "excludes": [],
                    })
            ar.create_archive(archive_path, entries)
            size_mb = archive_path.stat().st_size / (1024 * 1024)
            say(f"archive: {archive_path} ({size_mb:.1f} MB)")

            if dry_run:
                say("step 8/8: DRY-RUN - skipping upload + prune")
            else:
                say("step 8/8: uploading to remote ...")
                remote = rmod.get_remote(cfg)
                dest = remote.upload(archive_path, log_fp=log)
                say(f"uploaded: {dest}")

                keep = int(cfg.get("retention_weeks", 12))
                say(f"prune: keeping newest {keep} archives")
                deleted = rmod.prune(remote, system_name, keep, log_fp=log)
                for d in deleted:
                    say(f"  - deleted {d}")

            try:
                shutil.rmtree(work)
            except Exception as e:
                say(f"warning: could not remove build dir: {e}")

            say("=== DONE OK ===")
            return 0

        except Exception as e:
            say(f"ERROR: {e}")
            log.write(traceback.format_exc())
            log.flush()
            return 1


def _restore_md(system_name: str, ts: str) -> str:
    return (
        f"# RESTORE - {system_name} @ {ts} UTC\n"
        "\n"
        "Short version:\n"
        "1. Install matching PostgreSQL for fast physical restore, or matching/newer PostgreSQL for portable logical restore.\n"
        "2. Place this archive somewhere with ~2x its size free.\n"
        "3. Run `unpack.html` (the companion guide) or directly:\n"
        f"       py -3 restore.py --install {ts} --restore-mode auto\n"
        "4. Decrypt the .env: keep `secrets/env_key.bin` next to restore.py\n"
        "   (it was produced on the source machine).\n"
        "\n"
        "See unpack.html for the full layman walkthrough.\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a portable PG + app backup.")
    ap.add_argument("--config", help="Path to a config JSON file (default: config.<system>.json next to this script)")
    ap.add_argument("--dry-run", action="store_true", help="Build the archive locally but skip the upload.")
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
    return run(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
