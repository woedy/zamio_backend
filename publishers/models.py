import uuid
from django.db import models
from django.contrib.auth import get_user_model



User = get_user_model()



class PublisherInvitation(models.Model):
    track = models.ForeignKey('artists.Track', on_delete=models.CASCADE, related_name='publisher_invite')
    invited_by = models.ForeignKey('artists.Artist', on_delete=models.CASCADE)

    email = models.EmailField()
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')])
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    sent_on = models.DateTimeField(auto_now_add=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PublisherProfile(models.Model):

    ONBOARDING_STEPS = [
        ('profile', 'Complete Profile'),
        ('revenue-split', 'Revenue Split'),
        ('link-artist', 'Sign Link Artist'),
        ('payment', 'Add Payment Info'),

    ]

    publisher_id = models.CharField(max_length=255, blank=True, null=True, default=uuid.uuid4, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='publisher')
    
    company_name = models.CharField(max_length=255, null=True, blank=True)
    # Bank account can be optional during onboarding; allow blank
    bank_account = models.CharField(max_length=100, blank=True)
    # Mobile money account (optional)
    momo_account = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)

    verified = models.BooleanField(default=False)

    
    region = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    
    location_name = models.CharField(max_length=900, null=True, blank=True)
    lat = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)
    lng = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)
    
    writer_split = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, null=True, blank=True)
    publisher_split = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, null=True, blank=True)

    onboarding_step = models.CharField(max_length=20, choices=ONBOARDING_STEPS, default='profile')

    profile_completed = models.BooleanField(default=False)
    revenue_split_completed = models.BooleanField(default=False)
    link_artist_completed = models.BooleanField(default=False)
    payment_info_added = models.BooleanField(default=False)


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def get_next_onboarding_step(self):
        if not self.profile_completed:
            return 'profile'
        elif not self.revenue_split_completed:
            return 'revenue-split'
        elif not self.link_artist_completed:
            return 'link-artist'
        elif not self.payment_info_added:
            return 'payment'
       
        return 'done'


class PublishingAgreement(models.Model):
    publisher = models.ForeignKey(PublisherProfile, on_delete=models.CASCADE)
    songwriter = models.ForeignKey('artists.Artist', on_delete=models.CASCADE, related_name='published_songs')
    track = models.ForeignKey('artists.Track', on_delete=models.CASCADE)

    writer_share = models.DecimalField(max_digits=5, decimal_places=2)
    publisher_share = models.DecimalField(max_digits=5, decimal_places=2)

    contract_file = models.FileField(upload_to='contracts/', blank=True)
    verified_by_admin = models.BooleanField(default=False)

    agreement_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')])

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PublisherArtistRelationship(models.Model):
    """Enhanced publisher-artist relationship management"""
    RELATIONSHIP_TYPES = [
        ('exclusive', 'Exclusive Publishing'),
        ('co_publishing', 'Co-Publishing'),
        ('administration', 'Administration Only'),
        ('sub_publishing', 'Sub-Publishing'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending Approval'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ]
    
    publisher = models.ForeignKey(PublisherProfile, on_delete=models.CASCADE, related_name='artist_relationships')
    artist = models.ForeignKey('artists.Artist', on_delete=models.CASCADE, related_name='publisher_relationships')
    relationship_type = models.CharField(max_length=20, choices=RELATIONSHIP_TYPES, default='exclusive')
    
    # Territory and scope
    territory = models.CharField(max_length=100, default='Ghana')
    worldwide = models.BooleanField(default=False)
    
    # Financial terms
    royalty_split_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Publisher's percentage")
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    
    # Contract details
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    contract_file = models.FileField(upload_to='publisher_contracts/', blank=True)
    
    # Status and approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by_admin = models.BooleanField(default=False)
    approved_by_artist = models.BooleanField(default=False)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_relationships')
    notes = models.TextField(blank=True)
    
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('publisher', 'artist', 'territory')
        indexes = [
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['artist', 'status']),
            models.Index(fields=['status', 'start_date']),
        ]
    
    def __str__(self):
        return f"{self.publisher.company_name} - {self.artist.stage_name} ({self.relationship_type})"
    
    def is_active(self):
        """Check if relationship is currently active"""
        from django.utils import timezone
        today = timezone.now().date()
        
        return (
            self.status == 'active' and
            self.start_date <= today and
            (self.end_date is None or self.end_date >= today)
        )
    
    def activate_relationship(self):
        """Activate the relationship and update artist's status"""
        self.status = 'active'
        self.approved_by_admin = True
        self.approved_by_artist = True
        self.save()
        
        # Update artist's publisher relationship
        self.artist.update_publisher_relationship(
            publisher=self.publisher, 
            relationship_type='signed'
        )
    
    def terminate_relationship(self, reason=None):
        """Terminate the relationship and revert artist to self-published"""
        self.status = 'terminated'
        self.end_date = timezone.now().date()
        if reason:
            self.notes = f"{self.notes}\nTerminated: {reason}" if self.notes else f"Terminated: {reason}"
        self.save()
        
        # Revert artist to self-published
        self.artist.update_publisher_relationship(publisher=None)
    
    def clean(self):
        """Validate relationship data"""
        from django.core.exceptions import ValidationError
        
        if self.royalty_split_percentage < 0 or self.royalty_split_percentage > 100:
            raise ValidationError('Royalty split percentage must be between 0 and 100')
        
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError('End date must be after start date')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
