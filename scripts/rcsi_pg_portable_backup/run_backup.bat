@echo off
REM ---------------------------------------------------------------
REM   Double-click this to run a one-off portable backup NOW.
REM   All output goes to logs\backup_<timestamp>.log.
REM ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

REM Prefer the "py" launcher on Windows; fall back to "python".
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set PYRUN=py -3
) else (
    set PYRUN=python
)

echo === pg_portable_backup: running backup.py ===
%PYRUN% backup.py %*
set RC=%ERRORLEVEL%
echo.
if %RC%==0 (
    echo Backup finished successfully.
) else (
    echo Backup finished with exit code %RC% — check the newest logs\backup_*.log
)
echo.
pause
exit /b %RC%
