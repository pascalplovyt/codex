@echo off
setlocal
cd /d "%~dp0"
echo Running GitHub repo sync...
py -3 repo_sync.py --config config.json %*
echo.
echo Finished. Press any key to close.
pause >nul
