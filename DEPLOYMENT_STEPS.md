# 🚀 ZamIO Django Deployment Steps - Clear & Simple

**Follow these steps exactly to deploy your Django project locally and on Coolify.**

---

## 🖥️ **LOCAL DEVELOPMENT DEPLOYMENT**

### **Step 1: Prerequisites Check**
```bash
# Make sure you're in the right directory
cd zamio_backend

# Check if Docker is running
docker info

# Check if Docker Compose is available
docker-compose --version
```

**✅ Expected Result**: Docker info shows running status, docker-compose shows version

---

### **Step 2: Create Local Environment File**
```bash
# Copy the local environment template
copy env.local.example .env.local

# Verify the file was created
dir .env.local
```

**✅ Expected Result**: `.env.local` file exists in your directory

---

### **Step 3: Start Local Services**
```bash
# Start all local services
docker-compose -f docker-compose.local.yml up -d

# Wait for services to start (about 30 seconds)
```

**✅ Expected Result**: All containers start without errors

---

### **Step 4: Verify Services Are Running**
```bash
# Check container status
docker-compose -f docker-compose.local.yml ps

# You should see:
# - db (PostgreSQL) - Status: Up
# - redis - Status: Up  
# - zamio_app (Django) - Status: Up
# - celery_worker - Status: Up
# - celery_beat - Status: Up
```

**✅ Expected Result**: All 5 containers show "Up" status

---

### **Step 5: Test Your Application**
```bash
# Open your browser and go to:
# http://localhost:8001

# You should see Django welcome page or your app
```

**✅ Expected Result**: Django application loads in browser

---

### **Step 6: Run Django Commands**
```bash
# Run database migrations
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py migrate

# Create a superuser
docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py createsuperuser

# Collect static files
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py collectstatic --noinput
```

**✅ Expected Result**: Commands execute without errors

---

### **Step 7: Local Development Complete**
```bash
# Your local environment is now ready!
# Access points:
# - Django App: http://localhost:8001
# - PostgreSQL: localhost:5433
# - Redis: localhost:6380

# To stop services later:
docker-compose -f docker-compose.local.yml down
```

---

## 🌐 **PRODUCTION DEPLOYMENT ON COOLIFY**

### **Step 1: Prepare Production Environment**
```bash
# Make sure you're in the right directory
cd zamio_backend

# Copy production environment template
copy env.production.example .env

# Edit the .env file with your actual values
notepad .env
```

**🔑 IMPORTANT: Update these values in .env:**
- `SECRET_KEY=your-actual-secret-key-here`
- `EMAIL_HOST_USER=your-actual-email@gmail.com`
- `EMAIL_HOST_PASSWORD=your-actual-app-password`

---

### **Step 2: Test Production Build Locally**
```bash
# Build production Docker images
docker-compose build

# Test production services locally
docker-compose up -d

# Check if they start correctly
docker-compose ps

# Stop local production test
docker-compose down
```

**✅ Expected Result**: Production build completes without errors

---

### **Step 3: Commit and Push to Git**
```bash
# Add all files
git add .

# Commit changes
git commit -m "Production ready for Coolify deployment"

# Push to your repository
git push origin main
```

**✅ Expected Result**: Code is pushed to your Git repository

---

### **Step 4: Coolify Dashboard Setup**

#### **4.1 Create New Application**
1. Open Coolify dashboard in your browser
2. Click **"New Application"**
3. Choose **"Git Repository"**
4. Connect your Git repository
5. Select branch: `main`

#### **4.2 Configure Application Settings**
```
Application Name: zamio-django
Description: ZamIO Django Backend API
Port: 8000
```

#### **4.3 Enable Docker Compose**
```
Docker Compose: ✅ Enable
Compose File: docker-compose.yml
Main Service: zamio_app
```

---

### **Step 5: Set Environment Variables in Coolify**

**Add these one by one in Coolify:**

```bash
# Django Settings
DEBUG=False
DJANGO_SETTINGS_MODULE=core.settings
SECRET_KEY=your-actual-secret-key-from-env-file

# Database
DATABASE_URL=postgresql://zamio_prod_user:zamio_prod_password@db:5432/zamio_production

# Redis
REDIS_URL=redis://:zamio_redis_password@redis:6379/0

# Celery
CELERY_BROKER_URL=redis://:zamio_redis_password@redis:6379/0
CELERY_RESULT_BACKEND=redis://:zamio_redis_password@redis:6379/0

# Domain Configuration
ALLOWED_HOSTS=zamio.api.pleromaspringsfoundation.com,.pleromaspringsfoundation.com,pleromaspringsfoundation.com,localhost,zamio_app
CSRF_TRUSTED_ORIGINS=https://zamio.api.pleromaspringsfoundation.com,https://*.pleromaspringsfoundation.com,https://pleromaspringsfoundation.com
BASE_URL=https://zamio.api.pleromaspringsfoundation.com

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-actual-email@gmail.com
EMAIL_HOST_PASSWORD=your-actual-app-password
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Zamio <your-actual-email@gmail.com>
```

---

### **Step 6: Configure Domain and SSL**
```
Domain: zamio.api.pleromaspringsfoundation.com
SSL: ✅ Enable
SSL Provider: Let's Encrypt
Force HTTPS: ✅ Enable
```

---

### **Step 7: Deploy**
1. Click **"Deploy"** button
2. Monitor the build process
3. Wait for deployment to complete

**✅ Expected Result**: Build completes successfully, all services show "Running" status

---

### **Step 8: Post-Deployment Setup**
```bash
# Go to Coolify dashboard
# Click on your application
# Click "Terminal" tab
# Run these commands:

# Run database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Check Django configuration
python manage.py check --deploy
```

**✅ Expected Result**: All commands execute without errors

---

### **Step 9: Test Production Application**
```bash
# Open your browser and go to:
# https://zamio.api.pleromaspringsfoundation.com

# You should see your Django application
```

**✅ Expected Result**: Application loads successfully with HTTPS

---

## 🔍 **TROUBLESHOOTING CHECKLIST**

### **Local Development Issues**

#### **Docker Not Running**
```bash
# Start Docker Desktop
# Wait for it to fully start
# Try again
```

#### **Port Already in Use**
```bash
# Check what's using the ports
netstat -an | findstr :8001
netstat -an | findstr :5433
netstat -an | findstr :6380

# Kill conflicting processes or change ports
```

#### **Build Errors**
```bash
# Clean Docker cache
docker system prune -a

# Rebuild without cache
docker-compose -f docker-compose.local.yml build --no-cache
```

---

### **Production Deployment Issues**

#### **Build Fails in Coolify**
1. Check Coolify logs
2. Verify environment variables are set correctly
3. Ensure all required files are in Git repository

#### **Application Won't Start**
1. Check container logs in Coolify
2. Verify environment variables
3. Check if database and Redis are accessible

#### **Domain Not Accessible**
1. Verify DNS settings point to Coolify server
2. Check SSL certificate generation
3. Ensure firewall allows ports 80 and 443

---

## 📋 **DEPLOYMENT CHECKLIST**

### **Local Development**
- [ ] Docker Desktop is running
- [ ] `.env.local` file created
- [ ] All containers start successfully
- [ ] Django app accessible at http://localhost:8001
- [ ] Database migrations run without errors
- [ ] Superuser created successfully

### **Production Deployment**
- [ ] `.env` file configured with production values
- [ ] Production build tested locally
- [ ] Code committed and pushed to Git
- [ ] Coolify application created
- [ ] Environment variables set in Coolify
- [ ] Domain configured: zamio.api.pleromaspringsfoundation.com
- [ ] SSL enabled and working
- [ ] Deployment completed successfully
- [ ] Database migrations run in production
- [ ] Superuser created in production
- [ ] Application accessible at production URL

---

## 🆘 **GETTING HELP**

### **If Local Deployment Fails**
1. Check Docker status: `docker info`
2. Check container logs: `docker-compose -f docker-compose.local.yml logs -f`
3. Verify ports are available
4. Check `.env.local` file exists

### **If Production Deployment Fails**
1. Check Coolify build logs
2. Verify environment variables in Coolify
3. Check if all files are in Git repository
4. Verify domain DNS settings

### **Useful Commands**
```bash
# Check Docker status
docker info

# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Access container shell
docker-compose exec zamio_app bash
```

---

## 🎯 **EXPECTED TIMELINE**

- **Local Setup**: 15-30 minutes
- **Production Preparation**: 10-15 minutes
- **Coolify Configuration**: 10-15 minutes
- **Initial Deployment**: 10-20 minutes
- **Post-Deployment Setup**: 15-30 minutes
- **Total**: ~1-2 hours

---

## ✅ **SUCCESS INDICATORS**

### **Local Success**
- ✅ http://localhost:8001 loads your Django app
- ✅ All 5 containers show "Up" status
- ✅ Django commands run without errors

### **Production Success**
- ✅ https://zamio.api.pleromaspringsfoundation.com loads your app
- ✅ SSL certificate is valid (green lock in browser)
- ✅ All services running in Coolify dashboard
- ✅ Django commands work in Coolify terminal

---

**🎉 You're Ready to Deploy!**

Follow these steps exactly, and you'll have your ZamIO Django application running both locally and in production on Coolify!
