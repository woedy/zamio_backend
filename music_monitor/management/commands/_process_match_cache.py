# management/commands/process_matches.py

from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from django.db import models

from artists.models import Track
from music_monitor.models import MatchCache, PlayLog

class Command(BaseCommand):
    help = "Processes MatchCache entries and creates PlayLogs."

    def handle(self, *args, **kwargs):
        time_window = now() - timedelta(minutes=3)

        groups = (
            MatchCache.objects
            .filter(matched_at__gte=time_window)
            .values('track_id', 'station_id')
            .annotate(count=models.Count('id'))
        )

        for group in groups:
            if group['count'] < 3:
                continue  # Not enough matches

            matches = MatchCache.objects.filter(
                track_id=group['track_id'],
                station_id=group['station_id'],
                matched_at__gte=time_window
            ).select_related('track', 'station')

            start = matches.earliest('matched_at').matched_at
            stop = matches.latest('matched_at').matched_at
            duration = stop - start

            if duration.total_seconds() < 30:
                self.stdout.write(f"⏩ Skipped short match for track {group['track_id']} ({duration.total_seconds()}s)")
                continue

            try:
                track = Track.objects.get(id=group['track_id'])
            except Track.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Track {group['track_id']} not found. Skipping."))
                continue

            royalty = track.calculate_royalty(duration)
            confidence = matches.aggregate(avg=models.Avg('confidence_score'))['avg'] or 0.0

            # Avoid duplicates
            exists = PlayLog.objects.filter(
                track=track,
                station_id=group['station_id'],
                start_time__range=(start - timedelta(seconds=60), stop + timedelta(seconds=60))
            ).exists()

            if exists:
                self.stdout.write(f"🟡 Duplicate detected for {track.title}. Skipping.")
                continue

            PlayLog.objects.create(
                track=track,
                station_id=group['station_id'],
                start_time=start,
                stop_time=stop,
                duration=duration,
                royalty_amount=royalty,
                avg_confidence_score=confidence,
                source='Radio',
                flagged=confidence < 60  # Optional dispute flag
            )

            self.stdout.write(self.style.SUCCESS(f"✅ Logged play for {track.title}"))

            matches.delete()

        self.stdout.write("✅ Finished processing match cache.")
