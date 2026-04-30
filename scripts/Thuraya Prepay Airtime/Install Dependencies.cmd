@echo off
setlocal
cd /d "%~dp0"
echo Installing Thuraya Prepay Airtime Sales dependencies into the local vendor folder...
py -3 -m pip install --target "%~dp0vendor" -r requirements.txt
if errorlevel 1 (
  echo.
  echo Dependency installation failed.
  pause
  exit /b 1
)
echo.
echo Dependencies installed successfully.
pause
