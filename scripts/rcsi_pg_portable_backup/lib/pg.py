"""Wrappers around pg_dump / pg_restore / psql."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path


def _env_with_password(pg_cfg: dict) -> dict:
    env = os.environ.copy()
    pw = pg_cfg.get("password")
    if pw:
        env["PGPASSWORD"] = str(pw)
    env.setdefault("LC_MESSAGES", "C")
    return env


def _tool(pg_cfg: dict, name: str) -> str:
    bin_dir = pg_cfg.get("bin_dir")
    if bin_dir:
        exe = name + (".exe" if os.name == "nt" else "")
        p = Path(bin_dir) / exe
        if p.exists():
            return str(p)
    return name


def _base_args(pg_cfg: dict, include_db: bool = True) -> list:
    args = ["-h", str(pg_cfg.get("host", "localhost")),
            "-p", str(pg_cfg.get("port", 5432)),
            "-U", str(pg_cfg.get("user", "postgres"))]
    if include_db:
        args += ["-d", str(pg_cfg["database"])]
    return args


def dump_database(pg_cfg: dict, dump_path: Path, log_fp=None) -> None:
    dump_path = Path(dump_path)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_tool(pg_cfg, "pg_dump"), *_base_args(pg_cfg, include_db=True), "-Fc", "-Z", "6", "-v", "-f", str(dump_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp)


def dump_globals(pg_cfg: dict, out_path: Path, log_fp=None) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_tool(pg_cfg, "pg_dumpall"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "--globals-only",
           "-f", str(out_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp)


def database_exists(pg_cfg: dict, db_name: str, log_fp=None) -> bool:
    cmd = [_tool(pg_cfg, "psql"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", "postgres",
           "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"]
    result = subprocess.run(cmd, env=_env_with_password(pg_cfg), capture_output=True, text=True)
    if log_fp is not None:
        log_fp.write("> " + " ".join(cmd) + "\n")
        log_fp.write(result.stdout)
        log_fp.write(result.stderr)
    return result.stdout.strip().startswith("1")


def create_database(pg_cfg: dict, db_name: str, log_fp=None) -> None:
    cmd = [_tool(pg_cfg, "createdb"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           db_name]
    _run(cmd, _env_with_password(pg_cfg), log_fp)


def run_globals_sql(pg_cfg: dict, sql_path: Path, log_fp=None) -> None:
    cmd = [_tool(pg_cfg, "psql"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", "postgres",
           "-v", "ON_ERROR_STOP=0",
           "-f", str(sql_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp, allow_fail=True)


def restore_database(pg_cfg: dict, dump_path: Path, db_name: str, log_fp=None, drop_first: bool = False) -> None:
    dump_path = Path(dump_path)
    if drop_first and database_exists(pg_cfg, db_name, log_fp):
        drop_cmd = [_tool(pg_cfg, "dropdb"),
                    "-h", str(pg_cfg.get("host", "localhost")),
                    "-p", str(pg_cfg.get("port", 5432)),
                    "-U", str(pg_cfg.get("user", "postgres")),
                    db_name]
        _run(drop_cmd, _env_with_password(pg_cfg), log_fp)
    if not database_exists(pg_cfg, db_name, log_fp):
        create_database(pg_cfg, db_name, log_fp)
    cmd = [_tool(pg_cfg, "pg_restore"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", db_name,
           "--no-owner",
           "--no-privileges",
           "-v",
           str(dump_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp, allow_fail=True)


def server_version(pg_cfg: dict, log_fp=None) -> str:
    cmd = [_tool(pg_cfg, "psql"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", "postgres",
           "-tAc", "SELECT version()"]
    r = subprocess.run(cmd, env=_env_with_password(pg_cfg), capture_output=True, text=True)
    if log_fp is not None:
        log_fp.write("> " + " ".join(cmd) + "\n")
        log_fp.write(r.stdout)
        log_fp.write(r.stderr)
    out = (r.stdout or "").strip()
    return out or "unknown"


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _cluster_data_dir(cluster_cfg: dict) -> Path:
    data_dir = Path(cluster_cfg.get("data_dir") or "")
    if not data_dir:
        raise RuntimeError("local_cluster.data_dir is not configured")
    return data_dir


def _cluster_log_file(cluster_cfg: dict, data_dir: Path) -> Path:
    log_file = cluster_cfg.get("log_file")
    if log_file:
        return Path(log_file)
    return data_dir.parent / "logs" / "portable_backup_postgres.log"


def _cluster_start_options(pg_cfg: dict, cluster_cfg: dict) -> str:
    opts = (cluster_cfg.get("start_options") or "").strip()
    if opts:
        return opts
    return f"-p {pg_cfg.get('port', 5432)}"


def cluster_is_running(pg_cfg: dict, cluster_cfg: dict, log_fp=None) -> bool:
    data_dir = _cluster_data_dir(cluster_cfg)
    cmd = [_tool(pg_cfg, "pg_ctl"), "-D", str(data_dir), "status"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if log_fp is not None:
        log_fp.write("> " + " ".join(cmd) + "\n")
        log_fp.write(result.stdout or "")
        log_fp.write(result.stderr or "")
        log_fp.flush()
    if result.returncode == 0:
        return True
    return port_open(pg_cfg.get("host", "127.0.0.1"), int(pg_cfg.get("port", 5432)))


def stop_cluster(pg_cfg: dict, cluster_cfg: dict, log_fp=None) -> bool:
    data_dir = _cluster_data_dir(cluster_cfg)
    if not data_dir.exists():
        raise RuntimeError(f"cluster data_dir not found: {data_dir}")
    if not cluster_is_running(pg_cfg, cluster_cfg, log_fp):
        return False
    cmd = [_tool(pg_cfg, "pg_ctl"), "-D", str(data_dir), "-m", "fast", "-w", "stop"]
    _run(cmd, _env_with_password(pg_cfg), log_fp)
    return True


def start_cluster(pg_cfg: dict, cluster_cfg: dict, log_fp=None) -> None:
    data_dir = _cluster_data_dir(cluster_cfg)
    log_file = _cluster_log_file(cluster_cfg, data_dir)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _tool(pg_cfg, "pg_ctl"),
        "-D", str(data_dir),
        "-l", str(log_file),
        "-o", _cluster_start_options(pg_cfg, cluster_cfg),
        "start",
    ]
    env = _env_with_password(pg_cfg)
    if log_fp is not None:
        log_fp.write("> " + " ".join(cmd) + "\n")
        log_fp.flush()
    result = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def copy_cluster_data(cluster_cfg: dict, dst_dir: Path, log_fp=None) -> None:
    src = _cluster_data_dir(cluster_cfg)
    if not (src / "PG_VERSION").exists():
        raise RuntimeError(f"cluster data directory is not initialized: {src}")
    dst_dir = Path(dst_dir)
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    excludes = set(cluster_cfg.get("snapshot_excludes") or ["postmaster.pid"])

    def ignore(dirname, names):
        return [name for name in names if name in excludes]

    if log_fp is not None:
        log_fp.write(f"copy cluster {src} -> {dst_dir}\n")
        log_fp.flush()
    shutil.copytree(str(src), str(dst_dir), ignore=ignore)


def restore_cluster_data(cluster_cfg: dict, src_dir: Path, log_fp=None) -> None:
    src_dir = Path(src_dir)
    if not (src_dir / "PG_VERSION").exists():
        raise RuntimeError(f"snapshot data directory is not valid: {src_dir}")
    dst = _cluster_data_dir(cluster_cfg)
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if log_fp is not None:
        log_fp.write(f"restore cluster {src_dir} -> {dst}\n")
        log_fp.flush()
    shutil.copytree(str(src_dir), str(dst))


def wait_for_port(pg_cfg: dict, timeout_sec: int = 30) -> bool:
    deadline = time.time() + timeout_sec
    host = pg_cfg.get("host", "127.0.0.1")
    port = int(pg_cfg.get("port", 5432))
    while time.time() < deadline:
        if port_open(host, port):
            return True
        time.sleep(1)
    return False


def _run(cmd: list, env: dict, log_fp, allow_fail: bool = False) -> None:
    if log_fp is not None:
        log_fp.write("> " + " ".join(cmd) + "\n")
        log_fp.flush()
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    except FileNotFoundError as e:
        if log_fp is not None:
            log_fp.write(f"FileNotFoundError: {e}\n")
        raise
    if log_fp is not None:
        if result.stdout:
            log_fp.write(result.stdout)
        if result.stderr:
            log_fp.write(result.stderr)
        log_fp.flush()
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}")
