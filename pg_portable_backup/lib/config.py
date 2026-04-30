"""Configuration loader.

Reads a JSON config, strips ``_comment_*`` keys, resolves relative paths
against the backup script directory, and returns a plain dict. The rest
of the package treats this as the single source of truth.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent   # pg_portable_backup/


def _strip_comments(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("_comment")}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj]
    return obj


def _resolve(path_str: str, base: Path) -> Path:
    """Resolve a path that may be absolute or relative to *base*."""
    p = Path(path_str)
    if not p.is_absolute():
        p = base / p
    return p


def load(config_path: str | os.PathLike) -> dict:
    """Load a config file and normalise paths."""
    config_path = Path(config_path).resolve()
    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    cfg = _strip_comments(raw)

    # Root of this install; used to resolve "staging_dir", "logs_dir" etc.
    cfg["_root"] = str(ROOT)
    cfg["_config_path"] = str(config_path)

    cfg["staging_dir"] = str(_resolve(cfg.get("staging_dir", "staging"), ROOT))
    cfg["logs_dir"] = str(_resolve(cfg.get("logs_dir", "logs"), ROOT))
    cfg["secrets_dir"] = str(ROOT / "secrets")

    local_cluster = cfg.get("local_cluster")
    if isinstance(local_cluster, dict):
        if local_cluster.get("data_dir"):
            local_cluster["data_dir"] = str(_resolve(local_cluster["data_dir"], ROOT))
        if local_cluster.get("log_file"):
            local_cluster["log_file"] = str(_resolve(local_cluster["log_file"], ROOT))
        cfg["local_cluster"] = local_cluster

    # Source root defaults to current working dir if missing.
    if not cfg.get("source_root"):
        cfg["source_root"] = str(Path.cwd())

    # Make sure directories exist.
    for d in (cfg["staging_dir"], cfg["logs_dir"], cfg["secrets_dir"]):
        Path(d).mkdir(parents=True, exist_ok=True)

    return cfg


def find_default_config() -> Path | None:
    """If no config is given on the CLI, pick the first JSON we see."""
    candidates = sorted(ROOT.glob("config.*.json"))
    for c in candidates:
        if c.name != "config.example.json":
            return c
    if (ROOT / "config.example.json").exists():
        return ROOT / "config.example.json"
    return None
