@echo off
REM ZamIO Django Deployment Script for Coolify (Windows)
REM This script helps prepare your project for deployment

echo 🚀 ZamIO Django Deployment Preparation Script
echo ==============================================

REM Check if we're in the right directory
if not exist "manage.py" (
    echo ❌ Error: This script must be run from the Django project root directory
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

echo ✅ Docker is running

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: docker-compose is not installed. Please install it and try again.
    pause
    exit /b 1
)

echo ✅ docker-compose is available

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo 📝 Creating .env file from template...
    if exist "env.production.example" (
        copy "env.production.example" ".env" >nul
        echo ✅ .env file created from env.production.example
        echo ⚠️  Please edit .env file with your actual production values
    ) else (
        echo ❌ env.production.example not found. Please create .env manually.
    )
) else (
    echo ✅ .env file already exists
)

REM Check if .env has been customized
if exist ".env" (
    findstr "your-super-secret-key-here" .env >nul
    if not errorlevel 1 (
        echo ⚠️  Warning: .env file contains default values. Please customize them for production.
    )
)

REM Build Docker images
echo 🔨 Building Docker images...
docker-compose build

if errorlevel 1 (
    echo ❌ Docker build failed
    pause
    exit /b 1
)

echo ✅ Docker images built successfully

REM Check if all required files exist
echo 🔍 Checking required files...
set required_files=docker-compose.yml Dockerfile entrypoint.sh requirements.txt
for %%f in (%required_files%) do (
    if exist "%%f" (
        echo ✅ %%f exists
    ) else (
        echo ❌ %%f missing
        pause
        exit /b 1
    )
)

echo.
echo 🎉 Deployment preparation completed successfully!
echo.
echo 📋 Next steps:
echo 1. Edit .env file with your production values
echo 2. Commit and push your changes to Git
echo 3. Deploy to Coolify using the deployment guide
echo.
echo 📚 See COOLIFY_DEPLOYMENT.md for detailed deployment instructions
echo.
echo 🔧 To test locally: docker-compose up --build
echo.
pause
