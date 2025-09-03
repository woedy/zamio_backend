@echo off
echo Starting ZamIO Django Local Development Environment...
echo.

echo Checking if Docker is running...
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

echo Docker is running. Starting services...
echo.

echo Starting all local services...
docker-compose -f docker-compose.local.yml up -d

echo.
echo Services are starting up. Please wait a moment...
timeout /t 10 /nobreak >nul

echo.
echo Checking service status...
docker-compose -f docker-compose.local.yml ps

echo.
echo ========================================
echo Local Development Environment Started!
echo ========================================
echo.
echo Access your application at:
echo - Django App: http://localhost:9001
echo - PostgreSQL: localhost:9003
echo - Redis: localhost:9004
echo.
echo To stop services, run: docker-compose -f docker-compose.local.yml down
echo.
pause
