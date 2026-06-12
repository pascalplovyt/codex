"""Wrappers around pg_dump / pg_restore / psql.

All commands shell out to the binaries shipped with the PostgreSQL
server install. The one you care about is under
``C:\\Program Files\\PostgreSQL\\<N>\\bin`` on Windows. The config
key ``postgres.bin_dir`` tells us where that is.

We never hard-code a password on the command line. Instead we push
``PGPASSWORD`` into the environment of the child process, which is
the portable way to do this across every PG tool.
"""
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
    # Force English messages so our log is easier to grep.
    env.setdefault("LC_MESSAGES", "C")
    return env


def _tool(pg_cfg: dict, name: str) -> str:
    """Resolve a PostgreSQL binary (pg_dump / pg_restore / psql ...).

    Falls back to the bare name, so the tool is picked up from PATH
    if bin_dir is not set."""
    bin_dir = pg_cfg.get("bin_dir")
    if bin_dir:
        # Windows: executables are .exe. On Linux / Mac they have no extension.
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
    """pg_dump -Fc to *dump_path* (custom format, portable, compressed)."""
    dump_path = Path(dump_path)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_tool(pg_cfg, "pg_dump"),
           *_base_args(pg_cfg, include_db=True),
           "-Fc",            # custom format
           "-Z", "6",        # compression level
           "-v",             # verbose so the log is useful
           "-f", str(dump_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp)


def dump_globals(pg_cfg: dict, out_path: Path, log_fp=None) -> None:
    """pg_dumpall --globals-only  -> roles + tablespaces + grants."""
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
    """Ask the server whether *db_name* exists."""
    cmd = [_tool(pg_cfg, "psql"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", "postgres",
           "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"]
    result = subprocess.run(cmd, env=_env_with_password(pg_cfg),
                            capture_output=True, text=True)
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
    """Apply the globals dump into the new cluster. Ignores errors on
    roles that already exist (CREATE ROLE will fail if "postgres" is
    already there, and that is fine)."""
    cmd = [_tool(pg_cfg, "psql"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", "postgres",
           "-v", "ON_ERROR_STOP=0",
           "-f", str(sql_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp, allow_fail=True)


def restore_database(pg_cfg: dict, dump_path: Path, db_name: str,
                     log_fp=None, drop_first: bool = False) -> None:
    """pg_restore a custom-format dump into *db_name*.

    If drop_first is True and the DB already exists, we drop it. Otherwise
    we leave it alone and just restore into the existing (empty) DB."""
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
           "--no-owner",      # tolerate role mismatches on target
           "--no-privileges",
           "-v",
           str(dump_path)]
    _run(cmd, _env_with_password(pg_cfg), log_fp, allow_fail=True)


def server_version(pg_cfg: dict, log_fp=None) -> str:
    """Return 'PostgreSQL 17.x on ...' style string, or 'unknown'."""
    cmd = [_tool(pg_cfg, "psql"),
           "-h", str(pg_cfg.get("host", "localhost")),
           "-p", str(pg_cfg.get("port", 5432)),
           "-U", str(pg_cfg.get("user", "postgres")),
           "-d", "postgres",
           "-tAc", "SELECT version()"]
    r = subprocess.run(cmd, env=_env_with_password(pg_cfg),
                       capture_output=True, text=True)
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
        "-D",
        str(data_dir),
        "-l",
        str(log_file),
        "-o",
        _cluster_start_options(pg_cfg, cluster_cfg),
        "start",
    ]
    env = _env_with_password(pg_cfg)
    if log_fp is not None:
        log_fp.write("> " + " ".join(cmd) + "\n")
        log_fp.flush()
    result = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}"
        )


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
    """Run a command, stream its stdout+stderr into *log_fp*, raise on
    non-zero exit unless allow_fail."""
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
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}"
        )
