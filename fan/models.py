from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save

from core.utils import unique_fan_id_generator

User = get_user_model()

class Fan(models.Model):
    fan_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fans')
    username = models.CharField(max_length=255, blank=True, null=True)
    dob = models.DateTimeField(blank=True, null=True)

    phone = models.CharField(max_length=255, null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    location_name = models.CharField(max_length=900, null=True, blank=True)
    lat = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)
    lng = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)


    bio = models.TextField(blank=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    

def pre_save_fan_id_receiver(sender, instance, *args, **kwargs):
    if not instance.fan_id:
        instance.fan_id = unique_fan_id_generator(instance)

pre_save.connect(pre_save_fan_id_receiver, sender=Fan)


