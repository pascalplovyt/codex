@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 restore.py --config config.rcsi.json %*
) else (
  python restore.py --config config.rcsi.json %*
)
