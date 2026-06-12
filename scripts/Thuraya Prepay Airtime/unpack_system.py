from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ARCHIVES_DIR = Path(r"G:\My Drive\PG_Backups\codex_thuraya_rcs")
DEFAULT_TARGET_ROOT = Path.home() / "OneDrive" / "Documents" / "Codex" / "scripts"


def resolve_archive(selector: str) -> Path:
    if selector == "latest":
        archives = sorted(ARCHIVES_DIR.glob("thuraya_prepay_airtime_*.tar.gz"), reverse=True)
        if not archives:
            raise FileNotFoundError(f"No portable archives were found in {ARCHIVES_DIR}.")
        return archives[0]
    direct = Path(selector)
    if direct.exists():
        return direct.resolve()
    named = ARCHIVES_DIR / selector
    if named.exists():
        return named.resolve()
    raise FileNotFoundError(f"Archive not found: {selector}")


def load_json_member(tar: tarfile.TarFile, member_name: str) -> dict:
    member = tar.getmember(member_name)
    handle = tar.extractfile(member)
    if handle is None:
        raise RuntimeError(f"Could not read {member_name} from archive.")
    return json.loads(handle.read().decode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(bundle_root: Path, manifest: dict) -> None:
    for item in manifest.get("files", []):
        file_path = bundle_root / item["path"]
        if not file_path.exists():
            raise FileNotFoundError(f"Missing file after extraction: {item['path']}")
        actual_hash = sha256_file(file_path)
        if actual_hash != item["sha256"]:
            raise RuntimeError(f"Integrity check failed for {item['path']}")


def safe_remove_target(target_dir: Path, target_root: Path) -> None:
    resolved_target = target_dir.resolve()
    resolved_root = target_root.resolve()
    if resolved_root not in resolved_target.parents and resolved_target != resolved_root:
        raise RuntimeError(f"Refusing to remove target outside target root: {resolved_target}")
    shutil.rmtree(resolved_target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Unpack the Thuraya portable archive onto another computer.")
    parser.add_argument("--archive", default="latest", help="Archive selector: latest, filename, or full path.")
    parser.add_argument("--target-root", default=str(DEFAULT_TARGET_ROOT), help="Folder that should receive the project directory.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing files.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing target folder if it already exists.")
    args = parser.parse_args()

    archive_path = resolve_archive(args.archive)
    target_root = Path(args.target_root).expanduser()

    with tarfile.open(archive_path, "r:gz") as tar:
        metadata = load_json_member(tar, "metadata.json")
        manifest = load_json_member(tar, "manifest.json")

        project_dirname = metadata["project_dirname"]
        target_dir = target_root / project_dirname

        print(f"Archive: {archive_path}")
        print(f"Target root: {target_root}")
        print(f"Target project folder: {target_dir}")
        print(f"Database type: {metadata.get('database_type', 'sqlite')}")
        print(f"Entry point: {metadata.get('entrypoint', 'Launch Thuraya Prepay Airtime Sales.cmd')}")
        print(f"Files in manifest: {len(manifest.get('files', []))}")

        if args.dry_run:
            print("Dry-run complete. No files were extracted.")
            return 0

        if target_dir.exists():
            if not args.overwrite:
                raise FileExistsError(f"Target folder already exists: {target_dir}. Re-run with --overwrite if you really want to replace it.")
            safe_remove_target(target_dir, target_root)

        target_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="thuraya_unpack_", dir=str(ROOT)) as temp_dir:
            temp_path = Path(temp_dir)
            tar.extractall(temp_path)
            bundle_root = temp_path / "bundle"
            verify_manifest(bundle_root, manifest)
            shutil.copytree(bundle_root, target_dir)

    print("Portable archive restored successfully.")
    print(f"Project restored to: {target_dir}")
    print(f"Launch with: {target_dir / metadata.get('entrypoint', 'Launch Thuraya Prepay Airtime Sales.cmd')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
