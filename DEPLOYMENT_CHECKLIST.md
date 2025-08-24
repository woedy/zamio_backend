# 🚀 Coolify Deployment Checklist

## ✅ Pre-Deployment Verification

### 1. **Configuration Files** ✅
- [x] `nixpacks.toml` - Build configuration for Coolify
- [x] `Dockerfile` - Production-ready with Gunicorn
- [x] `requirements.txt` - All dependencies including `python-dotenv` and `dj-database-url`
- [x] `.dockerignore` - Optimized build context
- [x] `core/settings.py` - Environment variable support
- [x] `core/urls.py` - Health check endpoint at `/health/`

### 2. **Environment Variables** ⚠️ **REQUIRED IN COOLIFY**
You need to set these in Coolify dashboard:

#### **Essential Variables:**
```
DEBUG=False
SECRET_KEY=your-strong-secret-key-here
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DATABASE_URL=postgresql://username:password@host:port/database_name
REDIS_URL=redis://redis-host:6379/0
```

#### **Optional Variables:**
```
BASE_URL=https://your-domain.com
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 3. **Coolify Configuration** ⚠️ **REQUIRED SETUP**

#### **Build Settings:**
- **Build Pack**: Nixpacks
- **Build Command**: (Auto-detected from nixpacks.toml)
- **Start Command**: (Auto-detected from nixpacks.toml)

#### **Health Check:**
- **Health Check URL**: `/health/`
- **Health Check Interval**: 30 seconds
- **Health Check Timeout**: 10 seconds

#### **Port:**
- **Port**: 8000 (automatically set by Coolify)

### 4. **Database Setup** ⚠️ **REQUIRED**
- [ ] PostgreSQL database created and accessible
- [ ] `DATABASE_URL` environment variable set in Coolify
- [ ] Database credentials are secure

### 5. **Redis Setup** ⚠️ **REQUIRED**
- [ ] Redis service running and accessible
- [ ] `REDIS_URL` environment variable set in Coolify

## 🚀 **You're Ready to Deploy!**

### **Next Steps:**

1. **Set Environment Variables in Coolify:**
   - Go to your Coolify dashboard
   - Navigate to your application settings
   - Add all required environment variables

2. **Deploy:**
   - Push your code to your Git repository
   - Coolify will automatically detect the `nixpacks.toml` file
   - The build process will:
     - Install system dependencies (ffmpeg, libsndfile1, etc.)
     - Install Python dependencies
     - Run database migrations
     - Collect static files
     - Start with Gunicorn

3. **Monitor:**
   - Check the `/health/` endpoint
   - Monitor logs in Coolify dashboard
   - Verify all services are running

## 🔧 **If Deployment Fails:**

### **Common Issues:**
1. **Missing Environment Variables** - Check all required variables are set
2. **Database Connection** - Verify `DATABASE_URL` is correct
3. **Redis Connection** - Verify `REDIS_URL` is correct
4. **Port Issues** - Ensure port 8000 is available

### **Debug Steps:**
1. Check Coolify logs for specific error messages
2. Test health endpoint: `curl https://your-domain.com/health/`
3. Verify environment variables in Coolify dashboard
4. Check database and Redis connectivity

## 📋 **Final Status:**
✅ **Ready for Deployment** - All configuration files are in place!

⚠️ **Action Required**: Set environment variables in Coolify dashboard before deploying.
