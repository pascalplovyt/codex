from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
ARCHIVES_DIR = Path(r"G:\My Drive\PG_Backups\codex_thuraya_rcs")
DEFAULT_TARGET_ROOT = Path.home() / "OneDrive" / "Documents" / "Codex" / "scripts"


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
        threading.Thread(target=self._run, args=(command,), daemon=True).start()
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


def list_archives() -> list[dict]:
    items = []
    for path in sorted(ARCHIVES_DIR.glob("thuraya_prepay_airtime_*.tar.gz"), reverse=True):
        items.append({
            "name": path.name,
            "size": path.stat().st_size,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime)),
        })
    return items


def config_summary() -> dict:
    db_path = ROOT / "data" / "thuraya_airtime.sqlite3"
    return {
        "project_root": str(ROOT),
        "archive_dir": str(ARCHIVES_DIR),
        "default_target_root": str(DEFAULT_TARGET_ROOT),
        "database_type": "sqlite",
        "database_path": str(db_path),
        "database_exists": db_path.exists(),
        "entrypoint": "Launch Thuraya Prepay Airtime Sales.cmd",
        "installer": "Install Dependencies.cmd",
        "includes_vendor": (ROOT / "vendor").exists(),
    }


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
        route = urlparse(self.path).path or "/"
        if route in ("/", "/pack.html"):
            self._serve_file(ROOT / "pack.html")
            return
        if route == "/unpack.html":
            self._serve_file(ROOT / "unpack.html")
            return
        if route == "/api/config":
            self._json({"ok": True, "config": config_summary()})
            return
        if route == "/api/status":
            self._json({"ok": True, "job": JOB_MANAGER.status()})
            return
        if route == "/api/archives":
            self._json({"ok": True, "archives": list_archives()})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

    def do_POST(self) -> None:
        route = urlparse(self.path).path or "/"
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}

        if route == "/api/pack/run":
            command = [sys.executable, "-u", "pack_system.py"]
            if payload.get("dry_run"):
                command.append("--dry-run")
            ok, msg = JOB_MANAGER.start(command)
            self._json({"ok": ok, "message": msg}, status=200 if ok else 409)
            return

        if route == "/api/unpack/run":
            command = [
                sys.executable,
                "-u",
                "unpack_system.py",
                "--archive",
                str(payload.get("selector") or "latest"),
                "--target-root",
                str(payload.get("target_root") or DEFAULT_TARGET_ROOT),
            ]
            if payload.get("overwrite"):
                command.append("--overwrite")
            if payload.get("dry_run"):
                command.append("--dry-run")
            ok, msg = JOB_MANAGER.start(command)
            self._json({"ok": ok, "message": msg}, status=200 if ok else 409)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local UI server for the Thuraya portable pack/unpack kit.")
    parser.add_argument("--port", type=int, default=8792)
    parser.add_argument("--open", choices=["pack.html", "unpack.html"])
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    if args.open:
        def _open() -> None:
            time.sleep(1)
            webbrowser.open(f"http://127.0.0.1:{args.port}/{args.open}")
        threading.Thread(target=_open, daemon=True).start()

    print(f"Thuraya portable setup UI ready at http://127.0.0.1:{args.port}/")
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
