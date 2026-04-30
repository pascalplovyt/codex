@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -STA -File "%SCRIPT_DIR%OFBiz Windows Control Center.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo Control Center failed to open. Press any key to close this window.
    pause >nul
    exit /b %EXIT_CODE%
)
echo Opening dashboard in your browser...
start "" "http://127.0.0.1:8787/"
exit /b %EXIT_CODE%
