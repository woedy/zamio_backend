# models.py
from django.db import models
from django.contrib.auth import get_user_model

from artists.models import Track
from fun.models import Fun
from stations.models import Station, StationProgram

User = get_user_model()

class MatchCache(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="match_track")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="match_station")
    station_program = models.ForeignKey(StationProgram, null=True, blank=True, on_delete=models.SET_NULL,  related_name="match_station_program")

    matched_at = models.DateTimeField(auto_now_add=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    processed = models.BooleanField(default=False)

    

SOURCE_TYPE = (
    ('upload', 'upload'),
    ('streaming', 'streaming')

)
STATUS_TYPE = (
    ('Verified', 'Verified'),
    ('Flagged', 'Flagged'),
    ('Pending', 'Pending'),
    ('Dispute', 'Dispute'),
    ('Review', 'Review'),
    ('Resolved', 'Resolved')

)
class PlayLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_playlog")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="station_playlog")
    station_program = models.ForeignKey(StationProgram, on_delete=models.CASCADE, related_name="station_program_playlog", null=True, blank=True)
    
    source = models.CharField(max_length=100, choices=SOURCE_TYPE, blank=True, null=True)

    played_at = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    claimed = models.BooleanField(default=False)

    flagged = models.BooleanField(default=False)
    dispute_status = models.CharField(max_length=100, choices=STATUS_TYPE, blank=True, null=True)
    disput_comments = models.TextField(blank=True, null=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)





class StreamLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_streamlog")
    fun = models.ForeignKey(Fun, on_delete=models.CASCADE, null=True, blank=True, related_name="fun_playlog")
    

    played_at = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    claimed = models.BooleanField(default=False)

    flagged = models.BooleanField(default=False)
    dispute_status = models.CharField(max_length=100, choices=STATUS_TYPE, blank=True, null=True)
    disput_comments = models.TextField(blank=True, null=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)