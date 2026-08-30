@echo off
setlocal
cd /d "%~dp0"
set "EZZ_PHARMACY_DATA_DIR=%~dp0EzzPharmacyData"

echo ============================================
echo   Ezz Pharmacy - Local Offline Server
echo ============================================
echo.
echo Data folder: %EZZ_PHARMACY_DATA_DIR%
echo.
echo Local address: http://127.0.0.1:5000
echo Mobile devices on same Wi-Fi can use the PC IPv4 address shown below.
echo.
ipconfig | findstr /R /C:"IPv4 Address" /C:"IPv4-Adresse" /C:"Adresse IPv4"
echo.
echo Keep this window open while the system is running.
echo Press Ctrl+C to stop the server.
echo.
python app.py
if errorlevel 1 (
  echo.
  echo The application could not start.
  echo Make sure Python and the project dependencies are installed.
  pause
)
endlocal
