@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 portable_backup_server.py --open pack.html
) else (
  python portable_backup_server.py --open pack.html
)
