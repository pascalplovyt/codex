@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0vendor;%PYTHONPATH%"
py -3 app.py
if errorlevel 1 (
  echo.
  echo The app could not start. If dependencies are missing, run "Install Dependencies.cmd" first.
  pause
)
