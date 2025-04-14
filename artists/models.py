from django.db import models

class Artist(models.Model):
    name = models.CharField(max_length=255)
    stage_name = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='artist_profiles/', blank=True, null=True)
    spotify_url = models.URLField(blank=True, null=True)
    shazam_url = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.name

class Genre(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Album(models.Model):
    title = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
    release_date = models.DateField()
    cover_art = models.ImageField(upload_to='album_covers/')
    upc_code = models.CharField(max_length=30, unique=True, help_text="Universal Product Code")

    def __str__(self):
        return f"{self.title} - {self.artist.name}"

class Track(models.Model):
    title = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)

    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True, blank=True)
    
    audio_file = models.FileField(upload_to='tracks/')
    release_date = models.DateField()
    isrc_code = models.CharField(max_length=30, unique=True, help_text="International Standard Recording Code")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True)
    duration = models.DurationField(help_text="Track length")
    lyrics = models.TextField(blank=True, null=True)
    explicit = models.BooleanField(default=False)

    fingerprinted = models.BooleanField(default=False)
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)


    file_path = models.CharField(max_length=512)  # Path to the audio file

    def calculate_royalty(self, duration):

        rate_per_second = 0.01  # Example: 1 cent per second
        duration_seconds = duration.total_seconds()
        royalty_amount = duration_seconds * rate_per_second
        return round(royalty_amount, 2)

    def __str__(self):
        return f"{self.title} by {self.artist.name}"
    
    

class Contributor(models.Model):
    ROLE_CHOICES = [
        ('composer', 'Composer'),
        ('producer', 'Producer'),
        ('writer', 'Writer'),
        ('featured_artist', 'Featured Artist'),
        ('mixer', 'Mixer'),
        ('engineer', 'Engineer'),
    ]

    name = models.CharField(max_length=255)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='contributors')

    def __str__(self):
        return f"{self.name} ({self.role}) on {self.track.title}"

class PlatformAvailability(models.Model):
    PLATFORM_CHOICES = [
        ('spotify', 'Spotify'),
        ('shazam', 'Shazam'),
        ('apple_music', 'Apple Music'),
        ('youtube_music', 'YouTube Music'),
        ('tidal', 'Tidal'),
    ]
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    url = models.URLField()
    available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.track.title} on {self.platform}"
