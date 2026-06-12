"""Manifest generator.

Every archive contains a ``manifest.json`` at its root describing what
the archive is, where it came from, which Postgres version produced
the dump, what files are inside, and the SHA-256 of each file. The
restore script verifies hashes before applying anything."""
from __future__ import annotations

import hashlib
import json
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(p: Path, bufsize: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            h.update(chunk)
    return h.hexdigest()


def build(staging_dir: Path, cfg: dict, pg_version: str,
          extra: dict | None = None) -> dict:
    """Walk *staging_dir* and produce a manifest dict.

    *staging_dir* should already contain the database/app/schema/config
    subtrees that will go into the archive. We hash every file in it so
    the restore can verify. The manifest itself is then written INTO
    staging_dir so it ends up inside the archive."""
    staging_dir = Path(staging_dir)

    files = []
    for p in sorted(staging_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(staging_dir).as_posix()
            if rel == "manifest.json":
                continue   # we're about to overwrite it
            files.append({"path": rel,
                          "size": p.stat().st_size,
                          "sha256": sha256_file(p)})

    manifest = {
        "format_version":   1,
        "system_name":      cfg.get("system_name", "unknown"),
        "created_utc":      datetime.now(timezone.utc)
                                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_host":      socket.gethostname(),
        "source_platform":  f"{platform.system()} {platform.release()}",
        "postgres_server":  pg_version,
        "database":         cfg.get("postgres", {}).get("database"),
        "includes_globals": bool(cfg.get("postgres", {}).get("include_globals", True)),
        "env_encrypted":    True,
        "files":            files,
    }
    if extra:
        manifest.update(extra)
    return manifest


def write(manifest: dict, dst: Path) -> None:
    Path(dst).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def read(src: Path) -> dict:
    return json.loads(Path(src).read_text(encoding="utf-8"))


def verify(manifest: dict, root: Path) -> list:
    """Verify SHA-256 hashes of every file listed in the manifest.
    Returns a list of problem descriptions (empty == all good)."""
    problems = []
    root = Path(root)
    for entry in manifest.get("files", []):
        p = root / entry["path"]
        if not p.exists():
            problems.append(f"missing: {entry['path']}")
            continue
        actual = sha256_file(p)
        if actual != entry["sha256"]:
            problems.append(f"hash mismatch: {entry['path']}")
    return problems
