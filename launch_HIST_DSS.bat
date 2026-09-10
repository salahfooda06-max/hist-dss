@echo off
title HIST Tripoli - Decision Support System
echo ========================================
echo   HIST Decision Support System
echo   Starting server...
echo ========================================
echo.
echo After the server starts, open your browser and go to:
echo   http://localhost:5000
echo.
echo Press Ctrl+C to stop the server.
echo.

setlocal
set PORT=5000

:: Check if port is in use and try next available
netstat -ano | findstr :%PORT% >nul
if %errorlevel% == 0 (
    set /a PORT+=1
    echo Port 5000 is in use, trying port %PORT%...
)

start http://localhost:%PORT%
HIST_DSS.exe

endlocal
