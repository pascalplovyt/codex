"""Tiny Fernet-based symmetric encryption for the .env file.

The key lives at ``secrets/env_key.bin`` beside the backup scripts.
It is created automatically on first run if missing.

IMPORTANT for restore: the key file is NOT included in the archive.
The operator must copy ``secrets/env_key.bin`` to the destination
machine out-of-band (e.g. USB drive, password manager) or keep it
with the archive in a place only trusted people can see.
"""
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


def ensure_key(key_path: Path) -> bytes:
    """Load the Fernet key, generating it if the file does not exist."""
    key_path = Path(key_path)
    if key_path.exists():
        return key_path.read_bytes().strip()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        # Best-effort restrict (Windows will ignore most of this, but on
        # Linux/Mac it matters).
        key_path.chmod(0o600)
    except Exception:
        pass
    return key


def encrypt_file(src: Path, dst: Path, key: bytes) -> None:
    src = Path(src)
    dst = Path(dst)
    f = Fernet(key)
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    dst.write_bytes(f.encrypt(data))


def decrypt_file(src: Path, dst: Path, key: bytes) -> None:
    src = Path(src)
    dst = Path(dst)
    f = Fernet(key)
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    dst.write_bytes(f.decrypt(data))
