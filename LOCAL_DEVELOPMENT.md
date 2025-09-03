# 🖥️ ZamIO Django - Local Development Guide

**Complete guide for running ZamIO Django locally with Docker**

---

## 🚀 **Quick Start (Recommended)**

### **For Windows Users**
1. **Start Services**: Double-click `start-local.bat`
2. **Access App**: Open http://localhost:9001 in your browser
3. **Stop Services**: Double-click `stop-local.bat` when done

### **For Command Line Users**
```bash
# Start services
docker-compose -f docker-compose.local.yml up -d

# Access app
# Django: http://localhost:9001
# PostgreSQL: localhost:9003
# Redis: localhost:9004

# Stop services
docker-compose -f docker-compose.local.yml down
```

---

## 🔧 **What's Included**

### **Services**
- **Django App** (Port 9001): Your main application
- **PostgreSQL** (Port 9003): Database
- **Redis** (Port 9004): Cache and Celery broker
- **Celery Worker**: Background task processing
- **Celery Beat**: Scheduled task scheduler

### **Ports (All in 9000s)**
- **9001**: Django application
- **9003**: PostgreSQL database
- **9004**: Redis cache

---

## 📁 **Project Structure for Local Development**

```
zamio_backend/
├── docker-compose.local.yml  # Local services configuration
├── Dockerfile               # Simplified for local development
├── entrypoint.sh            # Container startup script
├── .env.local               # Local environment variables
├── start-local.bat          # Windows startup script
├── stop-local.bat           # Windows stop script
└── [your Django apps...]
```

---

## 🛠️ **Common Commands**

### **Django Management**
```bash
# Run migrations
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py migrate

# Create superuser
docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py createsuperuser

# Django shell
docker-compose -f docker-compose.local.yml exec -it zamio_app python manage.py shell

# Collect static files
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py collectstatic --noinput
```

### **Service Management**
```bash
# View logs
docker-compose -f docker-compose.local.yml logs -f zamio_app

# Restart a service
docker-compose -f docker-compose.local.yml restart zamio_app

# View running containers
docker-compose -f docker-compose.local.yml ps
```

---

## 🔍 **Troubleshooting**

### **Common Issues**

#### **Port Already in Use**
If you get port conflicts, check what's using the ports:
```bash
# Windows
netstat -ano | findstr :9001
netstat -ano | findstr :9003
netstat -ano | findstr :9004

# Stop conflicting processes or change ports in docker-compose.local.yml
```

#### **Database Connection Issues**
```bash
# Check if database is running
docker-compose -f docker-compose.local.yml ps db

# View database logs
docker-compose -f docker-compose.local.yml logs db
```

#### **Django Won't Start**
```bash
# Check Django logs
docker-compose -f docker-compose.local.yml logs zamio_app

# Run Django commands manually
docker-compose -f docker-compose.local.yml exec zamio_app python manage.py check
```

---

## 📝 **Environment Variables**

The `.env.local` file contains all necessary configuration:
- Database connection
- Redis connection
- Django settings
- Security keys

**⚠️ Never commit `.env.local` to version control!**

---

## 🎯 **Next Steps**

Once your local environment is running:

1. **Run Migrations**: Set up your database schema
2. **Create Superuser**: Access Django admin
3. **Explore the App**: Navigate to http://localhost:9001
4. **Check Celery**: Monitor background tasks
5. **Develop**: Make changes and see them live!

---

## 📚 **Additional Resources**

- **DEPLOYMENT_STEPS.md**: Detailed step-by-step guide
- **QUICK_COMMANDS.md**: Essential commands reference
- **DEPLOYMENT_CHECKLIST.md**: Deployment verification checklist

---

**Happy coding! 🎉**
