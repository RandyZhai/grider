@echo off
chcp 65001 >nul 2>&1
cd /d "D:\github\grider"
echo ========================================
echo   Rebuild & Restart Grider
echo ========================================
echo.
echo [1/2] Rebuilding image (with ETF search fix)...
docker compose build
if errorlevel 1 (
    echo [FAILED] Build failed!
    pause
    exit /b 1
)
echo.
echo [2/2] Restarting container...
docker compose up -d
timeout /t 5 /nobreak >nul
echo.
echo ========================================
echo   DONE! Testing search for 510300...
echo ========================================
docker exec grider python -c "
from backend.app.external.providers.akshare_provider import AkshareProvider
p = AkshareProvider()
result = p.search_by_ticker('510300')
print(f'Found {len(result[\"data\"])} results:')
for item in result['data']:
    print(f'  - {item[\"ticker\"]} {item[\"name\"]} ({item[\"type\"]})')
"
echo.
pause
