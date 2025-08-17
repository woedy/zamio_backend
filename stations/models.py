import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save

from core.utils import unique_station_id_generator

User = get_user_model()


def get_default_station_image():
    return "defaults/default_profile_image.png"




class Station(models.Model):
    ONBOARDING_STEPS = [
        ('profile', 'Complete Profile'),
        ('staff', 'Staff'),
        ('report', 'Report Method'),
        ('payment', 'Add Payment Info'),
    ]

    station_id = models.CharField(max_length=255, blank=True, null=True,  default=uuid.uuid4, unique=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='station_user')

    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='stations/', null=True, blank=True, default=get_default_station_image)
    phone = models.CharField(max_length=255, null=True, blank=True)
    
    city = models.CharField(max_length=255, null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    bank_account = models.CharField(max_length=100,  null=True, blank=True)
    momo_account = models.CharField(max_length=100,  null=True, blank=True)
    bio = models.TextField(blank=True, null=True)


    location_name = models.CharField(max_length=900, null=True, blank=True)
    lat = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)
    lng = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)

    avg_detection_confidence = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)

    about = models.TextField(blank=True, null=True)
    
    onboarding_step = models.CharField(max_length=20, choices=ONBOARDING_STEPS, default='profile')

    profile_completed = models.BooleanField(default=False)
    staff_completed = models.BooleanField(default=False)
    report_completed = models.BooleanField(default=False)
    payment_info_added = models.BooleanField(default=False)


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name
    

    
    def get_next_onboarding_step(self):
        if not self.profile_completed:
            return 'profile'
        elif not self.staff_completed:
            return 'staff'
        elif not self.report_completed:
            return 'report'
        elif not self.payment_info_added:
            return 'payment'
        return 'done'

    


# def pre_save_station_id_receiver(sender, instance, *args, **kwargs):
#     if not instance.station_id:
#         instance.station_id = unique_station_id_generator(instance)
# 
# pre_save.connect(pre_save_station_id_receiver, sender=Station)




class StationStreamLink(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='station_links')
    link = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StationProgram(models.Model):
    program_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)

    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='station_programs')
        
    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.program_name


ROLE_CHOICES = [
        ('Producer', 'Producer'),
        ('Presenter', 'Presenter'),
        ('Dj', 'Dj')
    ]


class ProgramStaff(models.Model):
    station_program = models.ForeignKey(StationProgram, on_delete=models.CASCADE, related_name='station_programs')
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name

