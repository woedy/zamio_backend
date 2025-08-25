@echo off
REM Django Command Runner Script for ZamIO Project (Windows)
REM This script helps run Django commands in Docker containers

setlocal enabledelayedexpansion

REM Colors for output (Windows 10+)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Function to print colored output
:print_status
echo %BLUE%[INFO]%NC% %~1
goto :eof

:print_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

REM Check if we're in the right directory
if not exist "manage.py" (
    echo %RED%[ERROR]%NC% This script must be run from the Django project root directory
    pause
    exit /b 1
)

REM Function to show usage
:show_usage
echo Usage: %0 [local^|prod] ^<django-command^>
echo.
echo Examples:
echo   %0 local makemigrations
echo   %0 local migrate
echo   %0 local createsuperuser
echo   %0 local shell
echo   %0 local collectstatic
echo   %0 prod makemigrations
echo   %0 prod migrate
echo   %0 prod createsuperuser
echo.
echo Available commands:
echo   makemigrations - Create database migrations
echo   migrate - Apply database migrations
echo   createsuperuser - Create admin user
echo   shell - Open Django shell
echo   collectstatic - Collect static files
echo   check - Check Django configuration
echo   runserver - Run development server (local only^)
echo   test - Run tests
echo   help - Show this help message
goto :eof

REM Check if command is provided
if "%~2"=="" (
    call :show_usage
    pause
    exit /b 1
)

set ENVIRONMENT=%~1
set COMMAND=%~2

REM Validate environment
if not "%ENVIRONMENT%"=="local" if not "%ENVIRONMENT%"=="prod" (
    echo %RED%[ERROR]%NC% Environment must be 'local' or 'prod'
    call :show_usage
    pause
    exit /b 1
)

REM Function to run command in local environment
:run_local
call :print_status "Running Django command in LOCAL environment..."

if "%COMMAND%"=="runserver" (
    call :print_status "Starting local development server..."
    docker-compose -f docker-compose.local.yml up zamio_app
) else if "%COMMAND%"=="makemigrations" (
    call :print_status "Creating database migrations..."
    docker-compose -f docker-compose.local.yml exec zamio_app python manage.py makemigrations
) else if "%COMMAND%"=="migrate" (
    call :print_status "Applying database migrations..."
    docker-compose -f docker-compose.local.yml exec zamio_app python manage.py migrate
) else if "%COMMAND%"=="createsuperuser" (
    call :print_status "Creating superuser..."
    docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py createsuperuser
) else if "%COMMAND%"=="shell" (
    call :print_status "Opening Django shell..."
    docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py shell
) else if "%COMMAND%"=="collectstatic" (
    call :print_status "Collecting static files..."
    docker-compose -f docker-compose.local.yml exec zamio_app python manage.py collectstatic --noinput
) else if "%COMMAND%"=="check" (
    call :print_status "Checking Django configuration..."
    docker-compose -f docker-compose.local.yml exec zamio_app python manage.py check
) else if "%COMMAND%"=="test" (
    call :print_status "Running tests..."
    docker-compose -f docker-compose.local.yml exec zamio_app python manage.py test
) else (
    call :print_status "Running custom command: %COMMAND%"
    docker-compose -f docker-compose.local.yml exec zamio_app python manage.py %COMMAND%
)
goto :eof

REM Function to run command in production environment
:run_prod
call :print_status "Running Django command in PRODUCTION environment..."

if "%COMMAND%"=="makemigrations" (
    call :print_status "Creating database migrations..."
    docker-compose exec zamio_app python manage.py makemigrations
) else if "%COMMAND%"=="migrate" (
    call :print_status "Applying database migrations..."
    docker-compose exec zamio_app python manage.py migrate
) else if "%COMMAND%"=="createsuperuser" (
    call :print_status "Creating superuser..."
    docker-compose exec -it zamio_app python manage.py createsuperuser
) else if "%COMMAND%"=="shell" (
    call :print_status "Opening Django shell..."
    docker-compose exec -it zamio_app python manage.py shell
) else if "%COMMAND%"=="collectstatic" (
    call :print_status "Collecting static files..."
    docker-compose exec zamio_app python manage.py collectstatic --noinput
) else if "%COMMAND%"=="check" (
    call :print_status "Checking Django configuration..."
    docker-compose exec zamio_app python manage.py check --deploy
) else if "%COMMAND%"=="test" (
    call :print_status "Running tests..."
    docker-compose exec zamio_app python manage.py test
) else (
    call :print_status "Running custom command: %COMMAND%"
    docker-compose exec zamio_app python manage.py %COMMAND%
)
goto :eof

REM Main execution
call :print_status "ZamIO Django Command Runner"
echo Environment: %ENVIRONMENT%
echo Command: %COMMAND%
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% docker-compose is not installed. Please install it and try again.
    pause
    exit /b 1
)

REM Execute based on environment
if "%ENVIRONMENT%"=="local" (
    REM Check if local compose file exists
    if not exist "docker-compose.local.yml" (
        echo %RED%[ERROR]%NC% docker-compose.local.yml not found. Please create it first.
        pause
        exit /b 1
    )
    
    REM Check if local services are running
    docker-compose -f docker-compose.local.yml ps | findstr "zamio_app" >nul
    if errorlevel 1 (
        echo %YELLOW%[WARNING]%NC% Local services are not running. Starting them...
        docker-compose -f docker-compose.local.yml up -d
        call :print_status "Waiting for services to be ready..."
        timeout /t 10 /nobreak >nul
    )
    
    call :run_local
) else (
    REM Check if production compose file exists
    if not exist "docker-compose.yml" (
        echo %RED%[ERROR]%NC% docker-compose.yml not found. Please create it first.
        pause
        exit /b 1
    )
    
    REM Check if production services are running
    docker-compose ps | findstr "zamio_app" >nul
    if errorlevel 1 (
        echo %RED%[ERROR]%NC% Production services are not running. Please start them first.
        pause
        exit /b 1
    )
    
    call :run_prod
)

call :print_success "Command completed successfully!"
pause
