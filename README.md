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
├── docker-compose.local.yml # Local development
├── .dockerignore           # Docker build exclusions
├── .gitignore              # Git exclusions
├── env.local.example       # Local environment template
├── .env.local              # Local environment (auto-created)
├── start-local.bat         # Windows startup script
├── stop-local.bat          # Windows stop script
├── DEPLOYMENT_STEPS.md     # Step-by-step deployment
├── DEPLOYMENT_CHECKLIST.md # Deployment checklist
├── QUICK_COMMANDS.md       # Essential commands
└── django-commands.bat     # Windows Django commands
```

---

## 🖥️ **Local Development**

### **Quick Start (Windows)**
```bash
# 1. Double-click start-local.bat
#    This will automatically:
#    - Check if Docker is running
#    - Start all services
#    - Show you the access URLs

# 2. Access your app
# Django: http://localhost:9001
# PostgreSQL: localhost:9003
# Redis: localhost:9004

# 3. To stop services
# Double-click stop-local.bat
```

### **Quick Start (Command Line)**
```bash
# 1. Create environment file
copy env.local.example .env.local

# 2. Start services
docker-compose -f docker-compose.local.yml up -d

# 3. Access your app
# Django: http://localhost:9001
# PostgreSQL: localhost:9003
# Redis: localhost:9004
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
