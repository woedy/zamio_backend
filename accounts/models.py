import os
import random
import uuid
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.authtoken.models import Token

from core.utils import unique_user_id_generator


def get_default_profile_image():
    return "defaults/default_profile_image.png"


def get_file_ext(filepath):
    base_name = os.path.basename(filepath)
    name, ext = os.path.splitext(base_name)
    return name, ext


def upload_image_path(instance, filename):
    new_filename = random.randint(1, 3910209312)
    name, ext = get_file_ext(filename)
    final_filename = '{new_filename}{ext}'.format(new_filename=new_filename, ext=ext)
    return "users/{final_filename}".format(
        final_filename=final_filename
    )


class UserManager(BaseUserManager):
    def create_user(self, email, first_name=None, last_name=None, password=None, is_active=True, is_staff=False, is_admin=False):
        if not email:
            raise ValueError("User must have an email address")
        if not password:
            raise ValueError("user must have a password")

        user_obj = self.model(
            email=self.normalize_email(email),
            first_name=first_name,
            last_name=last_name,
        )
        user_obj.set_password(password)
        user_obj.staff = is_staff
        user_obj.is_active = is_active
        user_obj.save(using=self._db)
        return user_obj


    def create_staffuser(self, email, first_name=None, last_name=None, password=None):
        user = self.create_user(
            email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True
        )
        return user



    def create_superuser(self, email, first_name=None, last_name=None, password=None, ):
        user = self.create_user(
            email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_admin=True
        )
        return user


    def search(self, query=None):
        qs = self.get_queryset()

        if query is not None:
            or_lookup = (Q(email__icontains=query) | Q(full_name__icontains=query))
            qs = qs.filter(or_lookup).distinct()

        return qs

GENDER_CHOICES = (
    ('Male', 'Male'),
    ('Female', 'Female'),

)



USER_TYPE = (
    ('Artist', 'Artist'),
    ('Station', 'Station'),
    ('Admin', 'Admin'),
    #('Fan', 'Fan'),
    ('Publisher', 'Publisher'),
    ('contributor', 'contributor'),

)

KYC_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
    ('incomplete', 'Incomplete'),
)


class User(AbstractBaseUser):
    user_id = models.UUIDField(blank=True, null=True, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    username = models.CharField(max_length=255, blank=True, null=True, unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to=upload_image_path, null=True, blank=True, default=get_default_profile_image)

    country = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=255, null=True, blank=True)

    user_type = models.CharField(max_length=100, choices=USER_TYPE, blank=True, null=True)
    
    # Enhanced authentication fields
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default='pending')
    kyc_documents = models.JSONField(default=dict, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)
    last_activity = models.DateTimeField(auto_now=True)
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    
    fcm_token = models.TextField(blank=True, null=True)
    otp_code = models.CharField(max_length=10, blank=True, null=True)
    email_token = models.CharField(max_length=10, blank=True, null=True)
    

    profile_complete = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)



    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)


    is_archived = models.BooleanField(default=False)

    staff = models.BooleanField(default=False)
    admin = models.BooleanField(default=False)

    timestamp = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    def __str__(self):
        return self.email


    def get_short_name(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True



    @property
    def is_staff(self):
        if self.is_admin:
            return True
        return self.staff


    @property
    def is_admin(self):
        return self.admin




@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


#def pre_save_user_id_receiver(sender, instance, *args, **kwargs):
#    if not instance.user_id:
#        instance.user_id = unique_user_id_generator(instance)
#
#pre_save.connect(pre_save_user_id_receiver, sender=User)





class UserContact(AbstractBaseUser):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_contacts')
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)




class UserEmergencyContact(AbstractBaseUser):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_emergency_contacts')
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserPermission(models.Model):
    """Granular permission management for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_permissions')
    permission = models.CharField(max_length=100)
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('user', 'permission')
        indexes = [
            models.Index(fields=['user', 'permission']),
            models.Index(fields=['permission']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.permission}"


class AuditLog(models.Model):
    """Comprehensive audit logging for all user actions and system events"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50, null=True, blank=True)
    resource_id = models.CharField(max_length=100, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    trace_id = models.UUIDField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['trace_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email if self.user else 'System'} - {self.action} at {self.timestamp}"