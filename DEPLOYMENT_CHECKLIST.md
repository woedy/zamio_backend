# 📋 ZamIO Django Deployment Checklist

**Print this and check off each step as you complete it!**

---

## 🖥️ **LOCAL DEVELOPMENT CHECKLIST**

### **Setup Phase**
- [ ] Docker Desktop is running
- [ ] You're in the `zamio_backend` directory
- [ ] Created `.env.local` file from template
- [ ] Started local services with `docker-compose -f docker-compose.local.yml up -d`

### **Verification Phase**
- [ ] All 5 containers show "Up" status
- [ ] Django app loads at http://localhost:8001
- [ ] Database migrations run successfully
- [ ] Superuser created successfully
- [ ] Static files collected successfully

**🎉 Local development is ready when all boxes are checked!**

---

## 🌐 **PRODUCTION DEPLOYMENT CHECKLIST**

### **Preparation Phase**
- [ ] Created `.env` file from production template
- [ ] Updated SECRET_KEY with strong value
- [ ] Updated email settings with real values
- [ ] Tested production build locally
- [ ] Committed and pushed code to Git

### **Coolify Setup Phase**
- [ ] Created new application in Coolify
- [ ] Connected Git repository
- [ ] Enabled Docker Compose
- [ ] Set compose file to `docker-compose.yml`
- [ ] Set main service to `zamio_app`

### **Environment Variables Phase**
- [ ] Set DEBUG=False
- [ ] Set DJANGO_SETTINGS_MODULE=core.settings
- [ ] Set SECRET_KEY (your actual key)
- [ ] Set DATABASE_URL
- [ ] Set REDIS_URL
- [ ] Set CELERY_BROKER_URL
- [ ] Set CELERY_RESULT_BACKEND
- [ ] Set ALLOWED_HOSTS
- [ ] Set CSRF_TRUSTED_ORIGINS
- [ ] Set BASE_URL
- [ ] Set EMAIL settings

### **Domain & SSL Phase**
- [ ] Set domain to `zamio.api.pleromaspringsfoundation.com`
- [ ] Enabled SSL with Let's Encrypt
- [ ] Enabled Force HTTPS

### **Deployment Phase**
- [ ] Clicked Deploy button
- [ ] Build completed successfully
- [ ] All services show "Running" status

### **Post-Deployment Phase**
- [ ] Ran database migrations in Coolify terminal
- [ ] Created superuser in Coolify terminal
- [ ] Collected static files in Coolify terminal
- [ ] Ran Django health check

### **Final Verification**
- [ ] Application loads at https://zamio.api.pleromaspringsfoundation.com
- [ ] SSL certificate is valid (green lock in browser)
- [ ] All Django functionality works
- [ ] Can access Coolify terminal and run Django commands

**🎉 Production deployment is complete when all boxes are checked!**

---

## 🆘 **TROUBLESHOOTING QUICK REFERENCE**

### **If Local Fails**
- [ ] Check Docker status: `docker info`
- [ ] Check container logs: `docker-compose -f docker-compose.local.yml logs -f`
- [ ] Verify ports are available
- [ ] Check `.env.local` file exists

### **If Production Fails**
- [ ] Check Coolify build logs
- [ ] Verify all environment variables are set
- [ ] Check if all files are in Git repository
- [ ] Verify domain DNS settings

---

## 📞 **SUPPORT RESOURCES**

- **Complete Guide**: `DEPLOYMENT_STEPS.md`
- **Quick Commands**: `QUICK_COMMANDS.md`
- **Docker Guide**: `README_DOCKER.md`
- **Coolify Guide**: `COOLIFY_DEPLOYMENT.md`

---

## 🎯 **EXPECTED TIMELINE**

- **Local Setup**: 15-30 minutes
- **Production Preparation**: 10-15 minutes  
- **Coolify Configuration**: 10-15 minutes
- **Initial Deployment**: 10-20 minutes
- **Post-Deployment Setup**: 15-30 minutes
- **Total**: ~1-2 hours

---

**🚀 You're ready to deploy! Follow the checklist step by step.**

**Remember**: Take your time, check each box, and don't skip steps!
