@echo off
setlocal
set TARGET_DIR=C:\Users\PASCA\OneDrive\Documents\Codex\scripts
echo Starting OFBiz dashboard...
"C:\Program Files\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -File "%TARGET_DIR%\start_local_ui.ps1"
if errorlevel 1 (
    echo.
    echo Dashboard failed to start. Please review the message above.
    pause
    exit /b %errorlevel%
)
start "" http://127.0.0.1:8787/
