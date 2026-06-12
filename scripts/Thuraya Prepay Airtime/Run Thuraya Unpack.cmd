@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 portable_setup_server.py --open unpack.html
) else (
  python portable_setup_server.py --open unpack.html
)
