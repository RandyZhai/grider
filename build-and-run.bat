@echo off
cd /d "D:\github\grider"
echo ============================================
echo   Building Docker Image with AKShare
echo ============================================
echo.
echo Start Time: %time%
echo.
docker compose build
echo.
echo End Time: %time%
echo.
if errorlevel 1 (
    echo [FAILED] Build failed!
) else (
    echo [SUCCESS] Build completed!
    echo.
    echo Now starting container...
    docker compose up -d
    echo.
    echo Waiting 8 seconds for service to start...
    timeout /t 8 /nobreak >nul
    echo.
    echo ============================================
    echo   CHECKING STATUS
    echo ============================================
    docker ps --filter "name=grider"
    echo.
    echo Logs (last 20 lines):
    docker compose logs --tail=20 grider
)
echo.
pause
