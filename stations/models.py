from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


def get_default_station_image():
    return "defaults/default_profile_image.png"




class Station(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='station_user')

    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='stations/', null=True, blank=True, default=get_default_station_image)
    phone = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    about = models.TextField(blank=True, null=True)


    location_name = models.CharField(max_length=200, null=True, blank=True)
    lat = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)
    lng = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)

        
    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name
    



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

