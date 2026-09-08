@echo off
chcp 65001 >nul 2>&1
title Grider Docker Deployment

echo ========================================
echo   Grider Docker Deployment (AKShare)
echo ========================================
echo.

:: 获取脚本所在目录的父目录（项目根目录）
set "PROJECT_DIR=%~dp0.."
for %%I in ("%PROJECT_DIR%") do set "PROJECT_DIR=%%~fI"

echo Changing to: %PROJECT_DIR%
cd /d "%PROJECT_DIR%"
echo Current directory: %cd%
echo.

echo [1/4] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not found!
    pause
    exit /b 1
)
echo [OK] Docker is ready
echo.

if not exist "docker-compose.yml" (
    echo [ERROR] docker-compose.yml not found in:
    echo   %cd%
    echo.
    echo Please run this script from the project folder.
    pause
    exit /b 1
)
echo [OK] Config file found
echo.

echo [2/4] Building Docker image with AKShare...
echo This may take 3-5 minutes, please wait...
echo.
docker compose build
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check errors above.
    pause
    exit /b 1
)
echo.
echo [OK] Build successful!
echo.

echo [3/4] Starting container...
docker compose up -d
if errorlevel 1 (
    echo [ERROR] Start failed!
    pause
    exit /b 1
)
echo.
echo [OK] Container started!
echo.

echo [4/4] Waiting for service ready...
timeout /t 8 /nobreak >nul
echo.
echo ========================================
echo   DEPLOYMENT COMPLETE!
echo ========================================
echo.
echo Service Info:
echo   - URL: http://localhost:5000
echo   - Container: grider
echo   - Data Source: AKShare (Sina/Tencent)
echo.
echo Useful Commands:
echo   - View logs: docker compose logs -f grider
echo   - Enter container: docker exec -it grider /bin/bash
echo   - Stop: docker compose down
echo   - Restart: docker compose restart
echo.
echo Container Status:
docker ps --filter "name=grider" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
