# 🚀 ZamIO Django Deployment Guide for Coolify

This guide will help you deploy your ZamIO Django project on Coolify with Docker and Docker Compose.

## 📋 Prerequisites

- Coolify instance running and accessible
- Domain `zamio.api.pleromaspringsfoundation.com` pointing to your Coolify server
- Git repository with your code
- Docker and Docker Compose installed on your local machine (for testing)

## 🔧 Local Testing (Optional)

Before deploying to Coolify, test locally:

```bash
# Clone your repository
git clone <your-repo-url>
cd zamio_backend

# Create environment file
cp env.production.example .env
# Edit .env with your actual values

# Build and run locally
docker-compose up --build
```

## 🚀 Coolify Deployment Steps

### 1. Connect Your Repository

1. In Coolify dashboard, go to **Applications** → **New Application**
2. Choose **Git Repository**
3. Connect your Git repository
4. Select the branch you want to deploy (usually `main` or `master`)

### 2. Configure Application Settings

**Basic Information:**
- **Name**: `zamio-django`
- **Description**: `ZamIO Django Backend API`
- **Port**: `8000`

**Build Configuration:**
- **Docker Compose**: Enable
- **Compose File**: `docker-compose.yml`
- **Main Service**: `zamio_app`

### 3. Set Environment Variables

Add these environment variables in Coolify:

```bash
# Django Settings
DEBUG=False
DJANGO_SETTINGS_MODULE=core.settings
SECRET_KEY=your-super-secret-key-here

# Database
DATABASE_URL=postgresql://zamio_postgres:zamio_postgres@db:5432/zamio_postgres

# Redis
REDIS_URL=redis://:zamio_redis_password@redis:6379/0

# Celery
CELERY_BROKER_URL=redis://:zamio_redis_password@redis:6379/0
CELERY_RESULT_BACKEND=redis://:zamio_redis_password@redis:6379/0

# Domain Configuration
ALLOWED_HOSTS=zamio.api.pleromaspringsfoundation.com,.pleromaspringsfoundation.com,pleromaspringsfoundation.com,localhost,zamio_app
CSRF_TRUSTED_ORIGINS=https://zamio.api.pleromaspringsfoundation.com,https://*.pleromaspringsfoundation.com,https://pleromaspringsfoundation.com
BASE_URL=https://zamio.api.pleromaspringsfoundation.com

# Email (update with your actual settings)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Zamio <your-email@gmail.com>
```

### 4. Configure Domain and SSL

1. **Domain**: Set to `zamio.api.pleromaspringsfoundation.com`
2. **SSL**: Enable automatic SSL with Let's Encrypt
3. **Force HTTPS**: Enable

### 5. Resource Allocation

**Memory**: Minimum 1GB, Recommended 2GB
**CPU**: Minimum 0.5 cores, Recommended 1 core

### 6. Deploy

1. Click **Deploy** in Coolify
2. Monitor the build and deployment process
3. Check logs for any errors

## 🔍 Post-Deployment Verification

### 1. Health Check

Visit: `https://zamio.api.pleromaspringsfoundation.com/`

Should return a Django response or your API endpoint.

### 2. Check Services

```bash
# Check if all containers are running
docker ps

# Check logs
docker-compose logs zamio_app
docker-compose logs db
docker-compose logs redis
```

### 3. Test API Endpoints

Test your main API endpoints to ensure they're working correctly.

## 🛠️ Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check if PostgreSQL container is running
   - Verify DATABASE_URL environment variable
   - Check database logs

2. **Redis Connection Failed**
   - Check if Redis container is running
   - Verify REDIS_URL environment variable
   - Check Redis logs

3. **Static Files Not Loading**
   - Ensure static files are collected: `python manage.py collectstatic`
   - Check STATIC_ROOT and STATIC_URL settings

4. **Domain Not Accessible**
   - Verify DNS settings point to Coolify server
   - Check SSL certificate generation
   - Verify Traefik labels in docker-compose.yml

### Debug Commands

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f zamio_app

# Access container shell
docker-compose exec zamio_app bash

# Check Django
docker-compose exec zamio_app python manage.py check --deploy
```

## 🔒 Security Considerations

1. **Change Default Passwords**: Update PostgreSQL and Redis passwords
2. **Secret Key**: Use a strong, unique SECRET_KEY
3. **Environment Variables**: Never commit sensitive data to Git
4. **Firewall**: Ensure only necessary ports are open
5. **Updates**: Keep dependencies updated

## 📈 Monitoring and Maintenance

1. **Logs**: Monitor application logs regularly
2. **Health Checks**: Set up external monitoring
3. **Backups**: Regular database and media backups
4. **Updates**: Regular security updates

## 🆘 Support

If you encounter issues:

1. Check Coolify logs
2. Verify environment variables
3. Test locally with Docker Compose
4. Check Django documentation
5. Review this deployment guide

---

**Happy Deploying! 🎉**

Your ZamIO Django application should now be accessible at `https://zamio.api.pleromaspringsfoundation.com`
