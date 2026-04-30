from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config as cfgmod
from lib import remote as rmod


ROOT = Path(__file__).resolve().parent
ARCHIVE_RE = re.compile(r"^(?P<system>[A-Za-z0-9_.\-]+)_(?P<ts>\d{8}T\d{6})\.tar\.gz$")


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job = {
            "running": False,
            "command": [],
            "lines": [],
            "exit_code": None,
            "started_at": None,
            "ended_at": None,
        }

    def status(self) -> dict:
        with self._lock:
            return dict(self._job, lines=list(self._job["lines"]))

    def start(self, command: list[str]) -> tuple[bool, str]:
        with self._lock:
            if self._job["running"]:
                return False, "Another job is already running."
            self._job = {
                "running": True,
                "command": command,
                "lines": [f"$ {' '.join(command)}"],
                "exit_code": None,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "ended_at": None,
            }
        thread = threading.Thread(target=self._run, args=(command,), daemon=True)
        thread.start()
        return True, "started"

    def _append(self, line: str) -> None:
        with self._lock:
            self._job["lines"].append(line.rstrip())
            self._job["lines"] = self._job["lines"][-400:]

    def _finish(self, exit_code: int) -> None:
        with self._lock:
            self._job["running"] = False
            self._job["exit_code"] = exit_code
            self._job["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def _run(self, command: list[str]) -> None:
        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            self._append(line)
        proc.wait()
        self._finish(proc.returncode)


JOB_MANAGER = JobManager()


def _python_command() -> list[str]:
    py_launcher = shutil.which("py")
    if py_launcher:
        try:
            result = subprocess.run(
                [py_launcher, "-3", "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                check=False,
            )
            resolved = (result.stdout or "").strip()
            if result.returncode == 0 and resolved:
                return [resolved, "-u"]
        except Exception:
            pass
        return [py_launcher, "-3", "-u"]
    return [sys.executable, "-u"]


def _default_config_path() -> Path:
    found = cfgmod.find_default_config()
    if not found:
        raise RuntimeError("No config file found next to portable_backup_server.py")
    return found


def _load_config_summary() -> dict:
    cfg_path = _default_config_path()
    cfg = cfgmod.load(cfg_path)
    remote = cfg.get("remote") or {}
    return {
        "config_path": str(cfg_path),
        "system_name": cfg.get("system_name"),
        "database": cfg.get("postgres", {}).get("database"),
        "host": cfg.get("postgres", {}).get("host"),
        "port": cfg.get("postgres", {}).get("port"),
        "source_root": cfg.get("source_root"),
        "env_file": cfg.get("env_file"),
        "remote_mode": remote.get("mode"),
        "remote_target": remote.get("gdrive_desktop_path") or remote.get("rclone_remote"),
        "has_fast_restore": bool((cfg.get("local_cluster") or {}).get("data_dir")),
        "cluster_data_dir": (cfg.get("local_cluster") or {}).get("data_dir"),
    }


def _list_archives() -> list[dict]:
    cfg = cfgmod.load(_default_config_path())
    remote = rmod.get_remote(cfg)
    items = []
    for name in remote.list():
        match = ARCHIVE_RE.match(name)
        if not match:
            continue
        if match.group("system") != cfg.get("system_name"):
            continue
        items.append({"timestamp": match.group("ts"), "name": name})
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        data = path.read_bytes()
        ctype = "text/html; charset=utf-8" if path.suffix == ".html" else "text/plain; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path or "/"
        if route in ("/", "/pack.html"):
            self._serve_file(ROOT / "pack.html")
            return
        if route == "/unpack.html":
            self._serve_file(ROOT / "unpack.html")
            return
        if route == "/api/config":
            self._json({"ok": True, "config": _load_config_summary()})
            return
        if route == "/api/status":
            self._json({"ok": True, "job": JOB_MANAGER.status()})
            return
        if route == "/api/archives":
            try:
                self._json({"ok": True, "archives": _list_archives()})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, status=500)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
        config_path = str(_default_config_path())

        if parsed.path == "/api/backup/run":
            command = _python_command() + ["backup.py", "--config", config_path]
            if payload.get("dry_run"):
                command.append("--dry-run")
            ok, msg = JOB_MANAGER.start(command)
            self._json({"ok": ok, "message": msg}, status=200 if ok else 409)
            return

        if parsed.path == "/api/restore/run":
            selector = payload.get("selector") or "latest"
            restore_mode = payload.get("restore_mode") or "auto"
            command = _python_command() + [
                "restore.py",
                "--config",
                config_path,
                "--install",
                str(selector),
                "--restore-mode",
                str(restore_mode),
                "-y",
            ]
            if payload.get("drop"):
                command.append("--drop")
            if payload.get("skip_app"):
                command.append("--skip-app")
            if payload.get("skip_env"):
                command.append("--skip-env")
            if payload.get("dry_run"):
                command.append("--dry-run")
            ok, msg = JOB_MANAGER.start(command)
            self._json({"ok": ok, "message": msg}, status=200 if ok else 409)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")


def main() -> int:
    ap = argparse.ArgumentParser(description="Local UI server for pg_portable_backup")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--open", choices=["pack.html", "unpack.html"], help="Open the chosen page in the default browser after the server starts.")
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    if args.open:
        def _open() -> None:
            time.sleep(1)
            webbrowser.open(f"http://127.0.0.1:{args.port}/{args.open}")
        threading.Thread(target=_open, daemon=True).start()

    print(f"pg_portable_backup UI ready at http://127.0.0.1:{args.port}/")
    print("Press Ctrl+C to stop the UI server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping UI server...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
