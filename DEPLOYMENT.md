# Zamio Backend Deployment Guide for Coolify

## Environment Variables Required

### Option 1: Using .env file (Recommended for local development)
1. Copy `env.example` to `.env`
2. Update the values in `.env` file
3. The application will automatically load these variables

### Option 2: Set environment variables in Coolify (Recommended for production)

Set these environment variables in your Coolify deployment:

### Basic Django Settings
```
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
BASE_URL=https://your-domain.com
```

### Database Configuration
```
DATABASE_URL=postgresql://username:password@host:port/database_name
```

### Redis Configuration
```
REDIS_URL=redis://redis-host:6379/0
```

### Email Configuration (Optional)
```
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_PORT=465
EMAIL_USE_SSL=True
```

## Coolify Configuration

### Build Configuration
- **Build Pack**: Nixpacks
- **Build Command**: Automatically handled by nixpacks.toml
- **Start Command**: Automatically handled by nixpacks.toml

### Health Check
- **Health Check URL**: `/health/`
- **Health Check Interval**: 30 seconds
- **Health Check Timeout**: 10 seconds

### Port Configuration
- **Port**: 8000 (automatically set by Coolify)

## Pre-deployment Checklist

1. ✅ **Environment Variables**: 
   - For local development: Copy `env.example` to `.env` and update values
   - For production: Set environment variables in Coolify dashboard
2. ✅ **Database Migration**: The build process will run migrations automatically
3. ✅ **Static Files**: Will be collected during build
4. ✅ **Dependencies**: All required packages are in requirements.txt
5. ✅ **Health Check**: Health endpoint is configured at `/health/`

## Local Development Setup

1. **Copy environment template:**
   ```bash
   cp env.example .env
   ```

2. **Update .env file with your local values:**
   ```bash
   # Edit .env file with your local database, Redis, and other settings
   nano .env
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Start development server:**
   ```bash
   python manage.py runserver
   ```

## Common Issues and Solutions

### 1. "Restarting (unhealthy)" Status
**Cause**: Application failing to start or health check failing
**Solution**: 
- Check logs for specific error messages
- Ensure all environment variables are set
- Verify database connection
- Check Redis connection

### 2. Database Connection Issues
**Cause**: Missing or incorrect DATABASE_URL
**Solution**: 
- Set proper DATABASE_URL environment variable
- Ensure database is accessible from the deployment

### 3. Redis Connection Issues
**Cause**: Missing or incorrect REDIS_URL
**Solution**:
- Set proper REDIS_URL environment variable
- Ensure Redis service is running and accessible

### 4. Static Files Issues
**Cause**: Static files not collected
**Solution**:
- Static files are automatically collected during build
- Check if STATIC_ROOT directory exists

### 5. Permission Issues
**Cause**: File permissions or missing dependencies
**Solution**:
- All system dependencies are included in nixpacks.toml
- Build process handles all necessary setup

## Monitoring

### Health Check Endpoint
- **URL**: `https://your-domain.com/health/`
- **Expected Response**: `{"status": "healthy", "message": "Django application is running"}`

### Logs
Monitor application logs in Coolify dashboard for:
- Django application errors
- Database connection issues
- Redis connection issues
- Static file serving issues

## Performance Optimization

### Gunicorn Configuration
- **Workers**: 3 (configurable in nixpacks.toml)
- **Timeout**: 120 seconds
- **Bind**: 0.0.0.0:$PORT

### Database Optimization
- Use connection pooling if needed
- Monitor query performance
- Consider read replicas for high traffic

### Caching
- Redis is configured for caching
- Django Redis cache backend is enabled
- Channel layers use Redis

## Security Considerations

1. **DEBUG**: Set to False in production
2. **SECRET_KEY**: Use a strong, unique secret key
3. **ALLOWED_HOSTS**: Restrict to your domain(s)
4. **HTTPS**: Enable SSL/TLS in Coolify
5. **Database**: Use strong passwords and restrict access

## Troubleshooting

### Check Application Logs
```bash
# In Coolify dashboard, check the logs tab
# Look for specific error messages
```

### Test Health Endpoint
```bash
curl https://your-domain.com/health/
```

### Verify Environment Variables
- Ensure all required environment variables are set
- Check for typos in variable names
- Verify variable values are correct

### Database Connection Test
```bash
# Test database connection (if you have access)
python manage.py dbshell
```

### Redis Connection Test
```bash
# Test Redis connection (if you have access)
redis-cli ping
```
