# streamer/models.py
from django.db import models

class StreamSource(models.Model):
    name = models.CharField(max_length=100)
    stream_url = models.URLField()
    is_active = models.BooleanField(default=True)

class AudioMatch(models.Model):
    track_title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    matched_at = models.DateTimeField(auto_now_add=True)
    confidence = models.FloatField()
    station = models.ForeignKey(StreamSource, on_delete=models.CASCADE)
    clip_file = models.FileField(upload_to='matched_clips/', null=True, blank=True)