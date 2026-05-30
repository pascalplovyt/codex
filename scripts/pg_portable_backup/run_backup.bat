@echo off
setlocal
title PASCA Combined Backup
cd /d "%~dp0"
set NO_PAUSE=0
set "BACKUP_ARGS="
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--no-pause" (
  set NO_PAUSE=1
  shift
  goto parse_args
)
if defined BACKUP_ARGS (
  set "BACKUP_ARGS=%BACKUP_ARGS% %1"
) else (
  set "BACKUP_ARGS=%1"
)
shift
goto parse_args
:args_done
echo ===============================================================
echo   PASCA Combined Backup - live run
echo ===============================================================
echo.
echo Working directory:
echo   %CD%
echo.
echo This will create live archives in G:\My Drive\PG_Backups.
echo Progress from each job will be shown below.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 backup_all.py %BACKUP_ARGS%
) else (
  python backup_all.py %BACKUP_ARGS%
)
set RC=%ERRORLEVEL%
echo.
echo ===============================================================
if "%RC%"=="0" (
  echo Combined backup finished successfully.
) else (
  echo Combined backup failed with exit code %RC%.
)
echo.
echo Status file:
echo   %CD%\latest_status.json
echo ===============================================================
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %RC%
