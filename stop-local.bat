@echo off
echo Stopping ZamIO Django Local Development Environment...
echo.

echo Stopping all local services...
docker-compose -f docker-compose.local.yml down

echo.
echo ========================================
echo Local Development Environment Stopped!
echo ========================================
echo.
echo All services have been stopped and containers removed.
echo.
echo To start services again, run: start-local.bat
echo.
pause
