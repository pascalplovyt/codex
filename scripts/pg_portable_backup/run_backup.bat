@echo off
setlocal
cd /d "%~dp0"
set "ARGS="
:parse
if "%~1"=="" goto run
if /I "%~1"=="--no-pause" shift & goto parse
set "ARGS=%ARGS% %1"
shift
goto parse
:run
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 backup_all.py %ARGS%
) else (
  python backup_all.py %ARGS%
)
set "RC=%ERRORLEVEL%"
exit /b %RC%
