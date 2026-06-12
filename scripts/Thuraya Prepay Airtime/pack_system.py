from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ARCHIVES_DIR = Path(r"G:\My Drive\PG_Backups\codex_thuraya_rcs")
SYSTEM_SLUG = "thuraya_prepay_airtime"
EXCLUDED_DIRS = {
    "__pycache__",
    "portable_archives",
    "portable_restore_staging",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def iter_project_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        if path.is_dir():
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix().lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_name() -> str:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{SYSTEM_SLUG}_{timestamp}.tar.gz"


def add_text_blob(tar: tarfile.TarFile, arcname: str, payload: dict) -> None:
    raw = json.dumps(payload, indent=2).encode("utf-8")
    info = tarfile.TarInfo(name=arcname)
    info.size = len(raw)
    info.mtime = int(datetime.now().timestamp())
    tar.addfile(info, io.BytesIO(raw))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack the Thuraya project into a portable archive.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be packed without writing an archive.")
    args = parser.parse_args()

    files = iter_project_files()
    archive_path = ARCHIVES_DIR / archive_name()
    metadata = {
        "system_name": SYSTEM_SLUG,
        "project_dirname": ROOT.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "entrypoint": "Launch Thuraya Prepay Airtime Sales.cmd",
        "database_type": "sqlite",
        "database_path": "data/thuraya_airtime.sqlite3",
        "notes": [
            "The portable kit includes the full project tree, local vendor dependencies, assets, and the SQLite database.",
            f"Portable archives are written to {ARCHIVES_DIR}.",
            "Sale files generated into Downloads are not inside the project folder and must be copied separately if needed.",
        ],
    }
    manifest = {
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ]
    }

    print(f"Project root: {ROOT}")
    print(f"Archive path: {archive_path}")
    print(f"Files to include: {len(files)}")
    for item in manifest["files"]:
        print(f" - {item['path']} ({item['size']} bytes)")

    if args.dry_run:
        print("Dry-run complete. No archive was written.")
        return 0

    ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        add_text_blob(tar, "metadata.json", metadata)
        add_text_blob(tar, "manifest.json", manifest)
        for path in files:
            tar.add(path, arcname=f"bundle/{path.relative_to(ROOT).as_posix()}")

    print(f"Portable archive created successfully: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
