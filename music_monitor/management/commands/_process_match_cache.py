# management/commands/process_matches.py

from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from django.db import models

from artists.models import Track
from music_monitor22.models import MatchCache, PlayLog

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        time_window = now() - timedelta(minutes=3)

        groups = (
            MatchCache.objects
            .filter(matched_at__gte=time_window)
            .values('track_id', 'station_id')
            .annotate(count=models.Count('id'))
        )

        for group in groups:
            if group['count'] >= 3:
                matches = MatchCache.objects.filter(
                    track_id=group['track_id'],
                    station_id=group['station_id'],
                    matched_at__gte=time_window
                )

                start = matches.earliest('matched_at').matched_at
                stop = matches.latest('matched_at').matched_at
                duration = stop - start

                if duration.total_seconds() >= 30:  # Only log if played for 30 seconds or more
                    track = Track.objects.get(id=group['track_id'])
                    royalty = track.calculate_royalty(duration)

                    # Avoid duplicate logs
                    exists = PlayLog.objects.filter(
                        track=track,
                        station_id=group['station_id'],
                        start_time__range=(start - timedelta(seconds=60), stop + timedelta(seconds=60))
                    ).exists()

                    if not exists:
                        PlayLog.objects.create(
                            track=track,
                            station_id=group['station_id'],
                            start_time=start,
                            stop_time=stop,
                            duration=duration,
                            royalty_amount=royalty
                        )
                        self.stdout.write(self.style.SUCCESS(f"Logged play for {track.title}"))

                # Clean up matches
                matches.delete()

        self.stdout.write("✅ Finished processing match cache.")
