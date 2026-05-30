"""Run every configured local backup job as one combined backup system."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / ".backup_all.lock"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_plan(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        plan = json.load(f)
    jobs = plan.get("jobs") or []
    if not jobs:
        raise RuntimeError(f"{path} has no jobs")
    return plan


def _resolve(path_text: str, base: Path) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = base / path
    return path


def _python_command() -> list[str]:
    if shutil.which("py"):
        return ["py", "-3"]
    return [sys.executable]


def _powershell_command() -> list[str]:
    pwsh = shutil.which("pwsh")
    if pwsh:
        return [pwsh]
    windows_pwsh = Path(r"C:\Program Files\PowerShell\7\pwsh.exe")
    if windows_pwsh.exists():
        return [str(windows_pwsh)]
    powershell = shutil.which("powershell")
    if powershell:
        return [powershell]
    return ["powershell"]


def _command_for_job(job: dict, dry_run: bool) -> tuple[list[str], Path, str]:
    job_type = job.get("type", "postgres")
    cwd = _resolve(job.get("working_directory", "."), ROOT)

    if job_type == "postgres":
        config_path = _resolve(job["config"], ROOT)
        command = [*_python_command(), str(ROOT / "backup.py"), "--config", str(config_path)]
        if dry_run:
            command.append("--dry-run")
        return command, cwd, str(config_path)

    if job_type == "python":
        script_path = _resolve(job["script"], ROOT)
        command = [*_python_command(), str(script_path)]
        command.extend(job.get("arguments", []))
        if dry_run:
            command.extend(job.get("dry_run_arguments", ["--dry-run"]))
        return command, cwd, str(script_path)

    if job_type == "powershell":
        script_path = _resolve(job["script"], ROOT)
        command = [
            *_powershell_command(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
        command.extend(job.get("arguments", []))
        if dry_run:
            command.extend(job.get("dry_run_arguments", ["-DryRun"]))
        return command, cwd, str(script_path)

    raise RuntimeError(f"Unsupported job type: {job_type}")


def _run_job(job: dict, dry_run: bool, log_fp) -> dict:
    name = job.get("name") or job.get("config") or job.get("script") or "backup job"
    command, cwd, target = _command_for_job(job, dry_run)

    started = _utc_now()
    log_fp.write(f"\n=== {name} started {started} ===\n")
    log_fp.write("> " + " ".join(command) + "\n")
    log_fp.flush()

    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"[{name}] {line}", end="")
        log_fp.write(line)
        log_fp.flush()
    return_code = proc.wait()
    finished = _utc_now()

    ok = return_code == 0
    log_fp.write(f"=== {name} finished {finished} rc={return_code} ===\n")
    log_fp.flush()
    return {
        "name": name,
        "type": job.get("type", "postgres"),
        "target": target,
        "started_utc": started,
        "finished_utc": finished,
        "return_code": return_code,
        "ok": ok,
    }


def run(plan_path: Path, dry_run: bool) -> int:
    plan = _load_plan(plan_path)
    logs_dir = _resolve(plan.get("logs_dir", "logs"), ROOT)
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    combined_log = logs_dir / f"combined_backup_{stamp}.log"

    status = {
        "started_utc": _utc_now(),
        "dry_run": dry_run,
        "plan": str(plan_path),
        "log": str(combined_log),
        "jobs": [],
    }

    rc = 0
    with combined_log.open("w", encoding="utf-8") as log_fp:
        for job in plan["jobs"]:
            result = _run_job(job, dry_run, log_fp)
            status["jobs"].append(result)
            if not result["ok"]:
                rc = 1

    status["finished_utc"] = _utc_now()
    status["ok"] = rc == 0
    status_path = _resolve(plan.get("status_file", "latest_status.json"), ROOT)
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(f"\nCombined backup {'OK' if rc == 0 else 'FAILED'}")
    print(f"Status: {status_path}")
    print(f"Log: {combined_log}")
    return rc


def _acquire_lock() -> bool:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(LOCK_PATH, flags)
    except FileExistsError:
        try:
            age_seconds = datetime.now(timezone.utc).timestamp() - LOCK_PATH.stat().st_mtime
        except OSError:
            age_seconds = 0
        if age_seconds > 12 * 60 * 60:
            LOCK_PATH.unlink(missing_ok=True)
            fd = os.open(LOCK_PATH, flags)
        else:
            print(f"Another combined backup appears to be running: {LOCK_PATH}")
            return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"pid": os.getpid(), "started_utc": _utc_now()}, indent=2))
    return True


def _release_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all configured portable backup jobs.")
    ap.add_argument("--plan", default="backup_all.json", help="Combined backup plan JSON.")
    ap.add_argument("--dry-run", action="store_true", help="Run each backup in dry-run mode.")
    args = ap.parse_args()
    if not _acquire_lock():
        return 0
    try:
        return run(_resolve(args.plan, ROOT), args.dry_run)
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
