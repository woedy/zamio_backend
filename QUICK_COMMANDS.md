# 🚀 Quick Commands Reference Card

**Essential commands for ZamIO Django deployment - keep this handy!**

---

## 🖥️ **LOCAL DEVELOPMENT - Quick Start**

### **Start Everything**
```bash
# Create environment file
copy env.local.example .env.local

# Start all services
docker-compose -f docker-compose.local.yml up -d

# Check status
docker-compose -f docker-compose.local.yml ps
```

### **Access Your App**
- **Django**: http://localhost:8001
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6380

### **Django Commands (Local)**
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

### **Stop Local Services**
```bash
docker-compose -f docker-compose.local.yml down
```

---

## 🌐 **PRODUCTION DEPLOYMENT - Quick Steps**

### **Prepare Production**
```bash
# Create production environment
copy env.production.example .env

# Edit .env with your values
notepad .env

# Test production build
docker-compose build
docker-compose up -d
docker-compose down
```

### **Deploy to Coolify**
1. **Git**: `git add . && git commit -m "Production ready" && git push origin main`
2. **Coolify**: Create app → Connect repo → Enable Docker Compose
3. **Environment Variables**: Copy from DEPLOYMENT_STEPS.md
4. **Domain**: `zamio.api.pleromaspringsfoundation.com`
5. **Deploy**: Click Deploy button

### **Post-Deployment Commands (Coolify Terminal)**
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static
python manage.py collectstatic --noinput

# Check health
python manage.py check --deploy
```

---

## 🔍 **TROUBLESHOOTING - Quick Fixes**

### **Check Status**
```bash
# Docker status
docker info

# Container status
docker-compose ps

# View logs
docker-compose logs -f
```

### **Common Issues**
```bash
# Port conflicts
netstat -an | findstr :8001

# Clean Docker
docker system prune -a

# Rebuild
docker-compose build --no-cache
```

---

## 📋 **ENVIRONMENT VARIABLES - Quick Copy**

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

## ✅ **SUCCESS CHECKLIST**

### **Local**
- [ ] http://localhost:8001 loads
- [ ] All 5 containers show "Up"
- [ ] Django commands work

### **Production**
- [ ] https://zamio.api.pleromaspringsfoundation.com loads
- [ ] SSL certificate valid
- [ ] All services running in Coolify

---

## 🆘 **NEED HELP?**

1. **Check logs**: `docker-compose logs -f`
2. **Verify environment**: Check `.env` files
3. **Check Docker**: `docker info`
4. **Review**: `DEPLOYMENT_STEPS.md`

---

**🎯 Keep this card open while deploying!**
