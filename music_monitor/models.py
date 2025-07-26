# models.py
from django.db import models
from django.contrib.auth import get_user_model

from artists.models import Track
from fan.models import Fan
from stations.models import Station, StationProgram

User = get_user_model()

class MatchCache(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="match_track")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="match_station")
    station_program = models.ForeignKey(StationProgram, null=True, blank=True, on_delete=models.SET_NULL,  related_name="match_station_program")

    matched_at = models.DateTimeField(auto_now_add=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    processed = models.BooleanField(default=False)
    failed_reason = models.TextField(null=True, blank=True)  # NEW field


    


class PlayLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_playlog")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="station_playlog")
    station_program = models.ForeignKey(StationProgram, on_delete=models.CASCADE, related_name="station_program_playlog", null=True, blank=True)
    
    source = models.CharField(max_length=50, choices=[('Radio', 'Radio'), ('Streaming', 'Streaming')])

    played_at = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    claimed = models.BooleanField(default=False)

    flagged = models.BooleanField(default=False)
 
    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class FailedPlayLog(models.Model):
    match = models.ForeignKey(MatchCache, on_delete=models.CASCADE)
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    will_retry = models.BooleanField(default=True)

    def __str__(self):
        return f"FailedPlayLog for MatchCache {self.match.id} at {self.timestamp}"


STATUS_TYPE = (
 
    ('Flagged', 'Flagged'),
    ('Pending', 'Pending'),
    ('Verified', 'Verified'),
    ('Resolving', 'Resolving'),
    ('Review', 'Review'),
    ('Resolved', 'Resolved')

)

class Dispute(models.Model):
    playlog = models.ForeignKey(PlayLog, on_delete=models.CASCADE, related_name="dispute_playlog")

    dispute_status = models.CharField(max_length=100, choices=STATUS_TYPE, blank=True, null=True)
    dispute_comments = models.TextField(blank=True, null=True)
    resolve_comments = models.TextField(blank=True, null=True)


    pending_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    resolving_time = models.DateTimeField(null=True, blank=True)
    review_time = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DurationField(null=True, blank=True)


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StreamLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_streamlog")
    fan = models.ForeignKey(Fan, on_delete=models.CASCADE, null=True, blank=True, related_name="fan_playlog")
    

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