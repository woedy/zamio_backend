# 🚀 ZamIO Django - Deployment Guide

**Complete guide for deploying ZamIO Django locally and on Coolify**

---

## 📁 **Project Structure**

```
zamio_backend/
├── core/                    # Django core settings
├── accounts/               # User accounts app
├── artists/                # Artists management
├── stations/               # Radio stations
├── music_monitor/          # Music monitoring
├── notifications/          # User notifications
├── publishers/             # Music publishers
├── fan/                    # Fan management
├── activities/             # User activities
├── bank_account/           # Banking features
├── mr_admin/               # Admin panel
├── streamer/               # Streaming features
├── users/                  # User management
├── templates/              # HTML templates
├── media/                  # User uploads
├── static_cdn/             # Static files
├── manage.py               # Django management
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker image
├── entrypoint.sh           # Container startup
├── docker-compose.yml      # Production services
├── docker-compose.local.yml # Local development
├── .dockerignore           # Docker build exclusions
├── .gitignore              # Git exclusions
├── env.local.example       # Local environment template
├── env.production.example  # Production environment template
├── DEPLOYMENT_STEPS.md     # Step-by-step deployment
├── DEPLOYMENT_CHECKLIST.md # Deployment checklist
├── QUICK_COMMANDS.md       # Essential commands
└── django-commands.bat     # Windows Django commands
```

---

## 🖥️ **Local Development**

### **Quick Start**
```bash
# 1. Create environment file
copy env.local.example .env.local

# 2. Start services
docker-compose -f docker-compose.local.yml up -d

# 3. Access your app
# Django: http://localhost:8001
# PostgreSQL: localhost:5433
# Redis: localhost:6380
```

### **Django Commands**
```bash
# Run migrations
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py migrate

# Create superuser
docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py createsuperuser

# Django shell
docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py shell

# Collect static
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py collectstatic --noinput
```

---

## 🌐 **Production Deployment (Coolify)**

### **1. Prepare Environment**
```bash
# Copy production template
copy env.production.example .env

# Edit with your values
notepad .env
```

### **2. Test Production Build**
```bash
# Build and test locally
docker-compose build
docker-compose up -d
docker-compose down
```

### **3. Deploy to Coolify**
1. **Git**: Commit and push your code
2. **Coolify**: Create app → Connect repo → Enable Docker Compose
3. **Environment**: Set variables from `env.production.example`
4. **Domain**: `zamio.api.pleromaspringsfoundation.com`
5. **Deploy**: Click Deploy button

### **4. Post-Deployment**
```bash
# In Coolify terminal:
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check --deploy
```

---

## 🔧 **Environment Variables**

### **Local (.env.local)**
```bash
DEBUG=True
DATABASE_URL=postgresql://zamio_user:zamio_password@db:5432/zamio_local
REDIS_URL=redis://redis:6379/0
```

### **Production (Coolify)**
```bash
DEBUG=False
SECRET_KEY=your-actual-secret-key
DATABASE_URL=postgresql://zamio_prod_user:zamio_prod_password@db:5432/zamio_production
REDIS_URL=redis://:zamio_redis_password@redis:6379/0
ALLOWED_HOSTS=zamio.api.pleromaspringsfoundation.com,.pleromaspringsfoundation.com,pleromaspringsfoundation.com,localhost,zamio_app
CSRF_TRUSTED_ORIGINS=https://zamio.api.pleromaspringsfoundation.com,https://*.pleromaspringsfoundation.com,https://pleromaspringsfoundation.com
BASE_URL=https://zamio.api.pleromaspringsfoundation.com
```

---

## 📋 **Quick Commands**

### **Start/Stop Services**
```bash
# Start local
docker-compose -f docker-compose.local.yml up -d

# Stop local
docker-compose -f docker-compose.local.yml down

# Start production
docker-compose up -d

# Stop production
docker-compose down
```

### **Check Status**
```bash
# Container status
docker-compose -f docker-compose.local.yml ps

# View logs
docker-compose -f docker-compose.local.yml logs -f

# Check Docker
docker info
```

---

## 🆘 **Troubleshooting**

### **Common Issues**
1. **Port Conflicts**: Check with `netstat -an | findstr :8001`
2. **Build Errors**: Clean with `docker system prune -a`
3. **Migration Issues**: Ensure all apps have migrations

### **Get Help**
- **Complete Guide**: `DEPLOYMENT_STEPS.md`
- **Checklist**: `DEPLOYMENT_CHECKLIST.md`
- **Commands**: `QUICK_COMMANDS.md`

---

## ✅ **Success Indicators**

### **Local Success**
- ✅ http://localhost:8001 loads
- ✅ All 5 containers show "Up"
- ✅ Django commands work

### **Production Success**
- ✅ https://zamio.api.pleromaspringsfoundation.com loads
- ✅ SSL certificate valid
- ✅ All services running in Coolify

---

## 🎯 **Expected Timeline**

- **Local Setup**: 15-30 minutes
- **Production Preparation**: 10-15 minutes
- **Coolify Configuration**: 10-15 minutes
- **Initial Deployment**: 10-20 minutes
- **Post-Deployment Setup**: 15-30 minutes
- **Total**: ~1-2 hours

---

**🚀 You're ready to deploy! Follow the guides and checklists for step-by-step instructions.**
