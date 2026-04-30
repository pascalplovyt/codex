import subprocess
import sys
from pathlib import Path


POWERSHELL = r"C:\Program Files\PowerShell\7\pwsh.exe"
DEFAULT_ACTIONS = {
    "launch dashboard": ["start_local_ui.ps1"],
    "stop dashboard": ["stop_local_ui.ps1"],
    "rebuild local clone": ["setup_local_clone.ps1"],
    "run full sync": ["sync_full.ps1"],
    "run incremental sync": ["sync_incremental.ps1"],
}


def resolve_workspace() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir, exe_dir.parent, exe_dir.parent.parent, Path.cwd()])
    else:
        script_dir = Path(__file__).resolve().parent
        candidates.extend([script_dir, Path.cwd()])

    for candidate in candidates:
        if (candidate / "start_local_ui.ps1").exists() and (candidate / "local_admin_server.py").exists():
            return candidate
    raise SystemExit("Unable to locate the OFBiz workspace next to this launcher.")


def normalized_name() -> str:
    return Path(sys.argv[0]).stem.lower().strip()


def infer_command():
    name = normalized_name()
    if name in DEFAULT_ACTIONS:
        return DEFAULT_ACTIONS[name]

    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: OFBizLocalControlCenter.exe [launch-dashboard|stop-dashboard|rebuild-local-clone|full-sync|incremental-sync]"
        )

    arg = sys.argv[1].strip().lower()
    mapping = {
        "launch-dashboard": ["start_local_ui.ps1"],
        "stop-dashboard": ["stop_local_ui.ps1"],
        "rebuild-local-clone": ["setup_local_clone.ps1"],
        "full-sync": ["sync_full.ps1", *sys.argv[2:]],
        "incremental-sync": ["sync_incremental.ps1", *sys.argv[2:]],
    }
    if arg not in mapping:
        raise SystemExit(f"Unknown action: {arg}")
    return mapping[arg]


def main():
    workspace = resolve_workspace()
    command_parts = infer_command()
    script_path = workspace / command_parts[0]
    if not script_path.exists():
        raise SystemExit(f"Required script not found: {script_path}")

    completed = subprocess.run(
        [POWERSHELL, "-ExecutionPolicy", "Bypass", "-File", str(script_path), *command_parts[1:]],
        cwd=str(workspace),
        check=False,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
