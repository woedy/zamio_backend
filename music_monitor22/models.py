# models.py
from django.db import models

from artists.models import Track
from stations.models import Station, StationProgram


class MatchCache(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    station_program = models.ForeignKey(StationProgram, on_delete=models.CASCADE)
    matched_at = models.DateTimeField(auto_now_add=True)

class PlayLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    station_program = models.ForeignKey(StationProgram, on_delete=models.CASCADE)

    start_time = models.DateTimeField()
    stop_time = models.DateTimeField()
    duration = models.DurationField()
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2)
