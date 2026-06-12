"""Remote storage — push/pull/prune archives on Google Drive.

Two modes, chosen via ``remote.mode`` in the config:

* ``gdrive_desktop`` — Google Drive for Desktop is installed and a
  letter like G:\\ is mapped. We just copy files into the synced
  folder. Simplest path; no API keys.
* ``rclone`` — run the ``rclone`` binary against a pre-configured
  remote (``rclone config`` done once by the operator).

Both modes implement the same ``upload / download / list / prune``
interface so the rest of the code doesn't care which is in use.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class RemoteError(RuntimeError):
    pass


def get_remote(cfg: dict):
    """Factory → returns a configured Remote object."""
    mode = (cfg.get("remote") or {}).get("mode", "gdrive_desktop")
    if mode == "gdrive_desktop":
        return GDriveDesktopRemote(cfg)
    if mode == "rclone":
        return RcloneRemote(cfg)
    raise RemoteError(f"Unknown remote.mode: {mode!r}")


# ---------------------------------------------------------------------------
# GDrive Desktop — just a file copy to the synced folder
# ---------------------------------------------------------------------------

class GDriveDesktopRemote:
    def __init__(self, cfg: dict):
        remote = cfg.get("remote") or {}
        self.path = Path(remote.get("gdrive_desktop_path") or "")
        if not self.path:
            raise RemoteError("remote.gdrive_desktop_path is empty")

    def _ensure(self, log_fp=None) -> None:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RemoteError(
                f"Cannot create GDrive folder {self.path}: {e}. "
                "Is Google Drive for Desktop running and the drive letter mounted?"
            )

    def upload(self, local: Path, log_fp=None) -> str:
        self._ensure(log_fp)
        dst = self.path / Path(local).name
        if log_fp is not None:
            log_fp.write(f"copy {local} -> {dst}\n")
            log_fp.flush()
        shutil.copy2(str(local), str(dst))
        return str(dst)

    def download(self, remote_name: str, local_dir: Path, log_fp=None) -> Path:
        src = self.path / remote_name
        if not src.exists():
            raise RemoteError(f"{remote_name} not found in {self.path}")
        dst = Path(local_dir) / remote_name
        if log_fp is not None:
            log_fp.write(f"copy {src} -> {dst}\n")
            log_fp.flush()
        shutil.copy2(str(src), str(dst))
        return dst

    def list(self, log_fp=None) -> list:
        if not self.path.exists():
            return []
        return sorted([p.name for p in self.path.iterdir() if p.is_file()])

    def delete(self, remote_name: str, log_fp=None) -> None:
        p = self.path / remote_name
        if p.exists():
            if log_fp is not None:
                log_fp.write(f"delete {p}\n")
            p.unlink()


# ---------------------------------------------------------------------------
# rclone — shells out to the rclone binary
# ---------------------------------------------------------------------------

class RcloneRemote:
    def __init__(self, cfg: dict):
        remote = cfg.get("remote") or {}
        self.binary = remote.get("rclone_binary") or "rclone"
        self.remote = remote.get("rclone_remote") or ""
        if not self.remote:
            raise RemoteError("remote.rclone_remote is empty")

    def _run(self, args: list, log_fp=None, capture=False):
        cmd = [self.binary] + args
        if log_fp is not None:
            log_fp.write("> " + " ".join(cmd) + "\n")
            log_fp.flush()
        if capture:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if log_fp is not None:
                log_fp.write(r.stdout or "")
                log_fp.write(r.stderr or "")
            if r.returncode != 0:
                raise RemoteError(f"rclone failed: {r.stderr or r.stdout}")
            return r.stdout
        r = subprocess.run(cmd)
        if r.returncode != 0:
            raise RemoteError(f"rclone failed with exit {r.returncode}")
        return ""

    def upload(self, local: Path, log_fp=None) -> str:
        self._run(["copy", "--progress", str(local), self.remote], log_fp)
        return f"{self.remote}/{Path(local).name}"

    def download(self, remote_name: str, local_dir: Path, log_fp=None) -> Path:
        self._run(["copy", "--progress",
                   f"{self.remote}/{remote_name}", str(local_dir)], log_fp)
        out = Path(local_dir) / remote_name
        if not out.exists():
            raise RemoteError(f"rclone: {remote_name} not downloaded")
        return out

    def list(self, log_fp=None) -> list:
        out = self._run(["lsf", self.remote], log_fp, capture=True)
        return sorted([ln.strip().rstrip("/") for ln in out.splitlines() if ln.strip()])

    def delete(self, remote_name: str, log_fp=None) -> None:
        self._run(["deletefile", f"{self.remote}/{remote_name}"], log_fp)


# ---------------------------------------------------------------------------
# Retention — called from backup.py after a successful upload
# ---------------------------------------------------------------------------

_ARCHIVE_RE = re.compile(r"^(?P<system>[A-Za-z0-9_.\-]+)_"
                         r"(?P<ts>\d{8}T\d{6})\.tar\.gz$")


def prune(remote, system_name: str, retention_weeks: int, log_fp=None) -> list:
    """Delete older archives on the remote belonging to *system_name*,
    keeping the newest ``retention_weeks`` (regardless of day-of-week).
    Returns the list of deleted names.
    """
    if retention_weeks <= 0:
        return []
    all_files = remote.list(log_fp)
    ours = []
    for name in all_files:
        m = _ARCHIVE_RE.match(name)
        if not m:
            continue
        if m.group("system") != system_name:
            continue
        try:
            ts = datetime.strptime(m.group("ts"), "%Y%m%dT%H%M%S")
        except ValueError:
            continue
        ours.append((ts, name))
    ours.sort(reverse=True)
    keep = ours[:retention_weeks]
    drop = ours[retention_weeks:]
    deleted = []
    for _, name in drop:
        try:
            remote.delete(name, log_fp)
            deleted.append(name)
        except Exception as e:
            if log_fp is not None:
                log_fp.write(f"prune: could not delete {name}: {e}\n")
    return deleted
