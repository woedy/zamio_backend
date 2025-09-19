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
        ('payment', 'Add Payment Info'),
    ]
    
    STATION_CLASSES = [
        ('class_a', 'Class A - Major Metropolitan'),
        ('class_b', 'Class B - Regional'),
        ('class_c', 'Class C - Local/Community'),
        ('online', 'Online Only'),
        ('community', 'Community/Non-Profit'),
    ]
    
    STATION_TYPES = [
        ('commercial', 'Commercial'),
        ('public', 'Public/Educational'),
        ('community', 'Community'),
        ('religious', 'Religious'),
        ('online', 'Online Only'),
    ]

    station_id = models.CharField(max_length=255, blank=True, null=True,  default=uuid.uuid4, unique=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='station_user')

    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='stations/', null=True, blank=True, default=get_default_station_image)
    phone = models.CharField(max_length=255, null=True, blank=True)
    
    city = models.CharField(max_length=255, null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    # Enhanced station classification for royalty calculation
    station_class = models.CharField(max_length=20, choices=STATION_CLASSES, default='class_c')
    station_type = models.CharField(max_length=20, choices=STATION_TYPES, default='commercial')
    license_number = models.CharField(max_length=50, null=True, blank=True, help_text="Broadcasting license number")
    coverage_area = models.CharField(max_length=100, null=True, blank=True, help_text="Coverage area description")
    estimated_listeners = models.IntegerField(null=True, blank=True, help_text="Estimated daily listeners")
    
    # Compliance and regulatory information
    regulatory_body = models.CharField(max_length=100, null=True, blank=True, help_text="e.g., GHAMRO, COSGA")
    compliance_contact_name = models.CharField(max_length=100, null=True, blank=True)
    compliance_contact_email = models.EmailField(null=True, blank=True)
    compliance_contact_phone = models.CharField(max_length=20, null=True, blank=True)
    
    # Operational details
    operating_hours_start = models.TimeField(null=True, blank=True)
    operating_hours_end = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default='Africa/Accra')
    website_url = models.URLField(null=True, blank=True)
    social_media_links = models.JSONField(default=dict, blank=True)
    
    # Technical specifications
    broadcast_frequency = models.CharField(max_length=20, null=True, blank=True, help_text="e.g., 101.5 FM")
    transmission_power = models.CharField(max_length=50, null=True, blank=True, help_text="e.g., 10kW")
    
    # Verification and approval
    verification_status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending Verification'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('suspended', 'Suspended')
        ], 
        default='pending'
    )
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_stations')
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(null=True, blank=True)

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


class StationStaff(models.Model):
    STAFF_ROLES = [
        ('manager', 'Station Manager'),
        ('producer', 'Producer'),
        ('presenter', 'Presenter'),
        ('dj', 'DJ'),
        ('engineer', 'Sound Engineer'),
        ('admin', 'Administrator'),
        ('compliance_officer', 'Compliance Officer'),
    ]
    
    PERMISSION_LEVELS = [
        ('view', 'View Only'),
        ('edit', 'Edit'),
        ('admin', 'Administrator'),
    ]

    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='station_staff')
    name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=50, choices=STAFF_ROLES, default='presenter')
    permission_level = models.CharField(max_length=20, choices=PERMISSION_LEVELS, default='view')
    
    # Contact and emergency information
    emergency_contact = models.CharField(max_length=100, null=True, blank=True)
    emergency_phone = models.CharField(max_length=20, null=True, blank=True)
    
    # Employment details
    hire_date = models.DateField(null=True, blank=True)
    employee_id = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    
    # Access control
    can_upload_playlogs = models.BooleanField(default=False)
    can_manage_streams = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['station', 'email']

    def __str__(self):
        return f"{self.name} - {self.role}"

