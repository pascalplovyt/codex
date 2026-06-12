"""Tar.gz archiver with exclude patterns.

We use the stdlib ``tarfile`` so there is no external dependency. A
custom filter function honours per-source ``exclude`` patterns (glob
style)."""
from __future__ import annotations

import fnmatch
import tarfile
from pathlib import Path


def _match_any(name: str, patterns: list) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def add_tree(tar: tarfile.TarFile, root: Path, arcroot: str,
             excludes: list) -> None:
    """Recursively add *root* to *tar*, honouring excludes.

    If *root* is a file, it is added as a single entry at arcroot.
    Excludes match the basename."""
    root = Path(root)
    if not root.exists():
        return
    if root.is_file():
        if _match_any(root.name, excludes):
            return
        tar.add(str(root), arcname=arcroot)
        return

    for p in sorted(root.rglob("*")):
        if _match_any(p.name, excludes):
            continue
        # Also check any parent dir name against excludes (so
        # __pycache__/foo.pyc is filtered whether we match pyc or not)
        if any(_match_any(part, excludes) for part in p.relative_to(root).parts):
            continue
        rel = p.relative_to(root)
        arcname = f"{arcroot}/{rel.as_posix()}"
        tar.add(str(p), arcname=arcname, recursive=False)


def create_archive(archive_path: Path, entries: list) -> None:
    """Write a tar.gz at *archive_path*.

    *entries* is a list of dicts::

        {"src": Path("..."), "arcroot": "database/cluster.dump", "excludes": []}
    """
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(archive_path), "w:gz") as tar:
        for e in entries:
            add_tree(tar, e["src"], e["arcroot"], e.get("excludes", []))


def extract_archive(archive_path: Path, out_dir: Path) -> None:
    archive_path = Path(archive_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(archive_path), "r:gz") as tar:
        # Safe extraction: refuse absolute paths and ../ escapes.
        members = []
        for m in tar.getmembers():
            name = m.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError(f"Refusing unsafe archive member: {name}")
            members.append(m)
        tar.extractall(str(out_dir), members=members)


def list_archive(archive_path: Path) -> list:
    with tarfile.open(str(archive_path), "r:gz") as tar:
        return tar.getnames()
