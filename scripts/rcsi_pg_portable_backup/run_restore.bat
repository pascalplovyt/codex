@echo off
REM ---------------------------------------------------------------
REM   Double-click this to restore from a backup.
REM   By default it lists available archives on the remote and then
REM   asks which one to install. Power users can pass CLI flags.
REM   All output goes to logs\restore_<timestamp>.log.
REM ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set PYRUN=py -3
) else (
    set PYRUN=python
)

if "%~1"=="" (
    echo === pg_portable_backup: available archives ===
    %PYRUN% restore.py --list
    echo.
    set /p CHOICE="Enter timestamp to install (or 'latest', or blank to quit): "
    if "%CHOICE%"=="" (
        echo no selection — exiting.
        pause
        exit /b 0
    )
    %PYRUN% restore.py --install "%CHOICE%"
) else (
    %PYRUN% restore.py %*
)

set RC=%ERRORLEVEL%
echo.
if %RC%==0 (
    echo Restore finished successfully.
) else (
    echo Restore finished with exit code %RC% — check logs\restore_*.log
)
echo.
pause
exit /b %RC%
