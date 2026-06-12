@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 restore.py --config config.codex.json %*
) else (
  python restore.py --config config.codex.json %*
)
