from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

STATUS_CHOICES = [
        ('Summary', 'Summary'),
        ('Compliance', 'Compliance'),
        ('Update', 'Update'),
    ]



class Notification(models.Model):
    title = models.CharField(max_length=1000, null=True, blank=True)
    type = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")

    message = models.TextField(null=True, blank=True)
    read = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



