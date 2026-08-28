@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Ezz Pharmacy - Local Order Follow-up v1.2.1

echo ==========================================
echo    Ezz Pharmacy - Local Order Follow-up System v1.2.1
echo ==========================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (
  where python >nul 2>&1
  if %errorlevel%==0 (set "PY=python") else (
    echo [ERROR] Python is not installed.
    echo Install Python 3 and try again.
    pause
    exit /b 1
  )
)

echo Checking local Python dependencies...
%PY% -c "from zoneinfo import ZoneInfo; import flask, openpyxl; ZoneInfo('Asia/Riyadh')" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python dependencies are missing.
  echo This launcher no longer tries to access the internet on every start.
  echo Connect to the internet once and run:
  echo   %PY% -m pip install -r requirements.txt
  echo Then run this file again.
  pause
  exit /b 1
)

%PY% -c "from zoneinfo import ZoneInfo; ZoneInfo('Asia/Riyadh'); print('Timezone OK')" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Asia/Riyadh timezone is unavailable.
  echo Try installing tzdata manually.
  pause
  exit /b 1
)

echo.
echo Starting system...
echo The browser will open automatically.
echo Do not close this window while the system is running.
echo Your data is stored outside this program folder, so new versions can be placed beside old versions safely.
echo.
%PY% app.py

echo.
echo The application stopped.
pause
