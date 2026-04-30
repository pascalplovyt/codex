@echo off
setlocal
set TARGET_DIR=C:\Users\PASCA\OneDrive\Documents\Codex\scripts
"C:\Program Files\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -File "%TARGET_DIR%\register_weekly_sync_task.ps1" %*
pause
