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
    bank_account = models.CharField(max_length=100, )
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