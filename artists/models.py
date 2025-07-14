from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save

from core.utils import unique_artist_id_generator, unique_contributor_id_generator, unique_track_id_generator
from fun.models import Fun

User = get_user_model()

class Artist(models.Model):
    artist_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='artists')
    stage_name = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True)
    total_earnings = models.CharField(max_length=255, blank=True, null=True)

    spotify_url = models.URLField(blank=True, null=True)
    shazam_url = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)

    followers = models.ManyToManyField(Fun,  related_name='followers')
    verified = models.BooleanField(default=False)

    region = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)


    location_name = models.CharField(max_length=900, null=True, blank=True)
    lat = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)
    lng = models.DecimalField(default=0.0, max_digits=50, decimal_places=20, null=True, blank=True)


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    

def pre_save_artist_id_receiver(sender, instance, *args, **kwargs):
    if not instance.artist_id:
        instance.artist_id = unique_artist_id_generator(instance)

pre_save.connect(pre_save_artist_id_receiver, sender=Artist)








class Genre(models.Model):
    name = models.CharField(max_length=100)
    
    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name



def get_default_album_cover_image():
    return "defaults/default_album_cover_image.png"


class Album(models.Model):
    title = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
    release_date = models.DateField(null=True, blank=True)
    cover_art = models.ImageField(upload_to='album_covers/', default=get_default_album_cover_image)
    upc_code = models.CharField(null=True, max_length=30, unique=True, help_text="Universal Product Code")

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.artist.stage_name}"
    



class ArtistGenre(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name


def get_default_track_cover_image():
    return "defaults/default_track_cover_image.png"


STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

class Track(models.Model):
    track_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    title = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)

    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True, blank=True)
    
    cover_art = models.ImageField(upload_to='track_covers/', default=get_default_track_cover_image)

    audio_file = models.FileField(upload_to='tracks/')
    
    audio_file_mp3 = models.FileField(upload_to='tracks/mp3/', null=True, blank=True)
    audio_file_wav = models.FileField(upload_to='tracks/wav/', null=True, blank=True)

    release_date = models.DateField(blank=True, null=True)
    isrc_code = models.CharField(max_length=30, unique=True, null=True, blank=True, help_text="International Standard Recording Code")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True)
    duration = models.DurationField(help_text="Track length", null=True, blank=True)
    lyrics = models.TextField(blank=True, null=True)
    explicit = models.BooleanField(default=False)

    fingerprinted = models.BooleanField(default=False)
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_royalty(self, duration):

        rate_per_second = 0.01  # Example: 1 cent per second
        duration_seconds = duration.total_seconds()
        royalty_amount = duration_seconds * rate_per_second
        return round(royalty_amount, 2)



def pre_save_track_id_receiver(sender, instance, *args, **kwargs):
    if not instance.track_id:
        instance.track_id = unique_track_id_generator(instance)

pre_save.connect(pre_save_track_id_receiver, sender=Track)



    

class Contributor(models.Model):
    ROLE_CHOICES = [
        ('Composer', 'Composer'),
        ('Producer', 'Producer'),
        ('Writer', 'Writer'),
        ('Featured Artist', 'Featured Artist'),
        ('Mixer', 'Mixer'),
        ('Engineer', 'Engineer'),
    ]

    contributor_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    name = models.CharField(max_length=255)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='contributors')
    percent_split = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.role}) on {self.track.title}"




def pre_save_track_contributor_id_receiver(sender, instance, *args, **kwargs):
    if not instance.contributor_id:
        instance.contributor_id = unique_contributor_id_generator(instance)

pre_save.connect(pre_save_track_contributor_id_receiver, sender=Contributor)





class PlatformAvailability(models.Model):
    PLATFORM_CHOICES = [
        ('Spotify', 'Spotify'),
        ('Shazam', 'Shazam'),
        ('Apple Music', 'Apple Music'),
        ('YouTube Music', 'YouTube Music'),
        ('Tidal', 'Tidal'),
    ]
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    url = models.URLField()
    available = models.BooleanField(default=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.track.title} on {self.platform}"




class TrackFeedback(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_feedback")
    fun = models.ForeignKey(Fun, on_delete=models.CASCADE, related_name='fun_feedback')
    feedback = models.TextField(null=True, blank=True)
    rating = models.IntegerField(default=0)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



#####################
####FINGERPRINTING #####
##################################


class Fingerprint(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="fingerprint_track")
    #hash = models.BinaryField(db_index=True)  # Stores BYTEA in PostgreSQL, BLOB in SQLite
    hash = models.CharField(max_length=20, db_index=True)

    offset = models.IntegerField()
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['hash', 'track_id'])
        ]
        unique_together = ('track', 'offset', 'hash')
