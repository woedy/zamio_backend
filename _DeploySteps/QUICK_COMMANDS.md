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
- **Django**: http://localhost:9001
- **PostgreSQL**: localhost:9003
- **Redis**: localhost:9004

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