from django.core.management.base import BaseCommand
from api.models import Track
from dejavu import Dejavu
from dejavu_config import config

class Command(BaseCommand):
    help = "Fingerprint all unfingerprinted tracks"

    def handle(self, *args, **kwargs):
        djv = Dejavu(config)
        unfingerprinted = Track.objects.filter(fingerprinted=False)

        if not unfingerprinted.exists():
            self.stdout.write(self.style.SUCCESS("No new tracks to fingerprint."))
            return

        for track in unfingerprinted:
            try:
                self.stdout.write(f"Fingerprinting: {track.title}")
                djv.fingerprint_file(track.audio_file.path)
                track.fingerprinted = True
                track.save()
                self.stdout.write(self.style.SUCCESS(f"✓ Fingerprinted: {track.title}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error with {track.title}: {str(e)}"))








###############

class Command(BaseCommand):
    help = "Process match cache and create PlayLogs"

    def handle(self, *args, **kwargs):
        from django.utils.timezone import now, timedelta
        from api.models import MatchCache, PlayLog

        time_window = now() - timedelta(minutes=3)

        matches = (
            MatchCache.objects
            .filter(matched_at__gte=time_window)
            .values('track_id', 'station_id')
            .annotate(count=models.Count('id'))
        )

        for group in matches:
            if group['count'] >= 3:
                hits = MatchCache.objects.filter(
                    track_id=group['track_id'],
                    station_id=group['station_id'],
                    matched_at__gte=time_window
                )
                start = hits.earliest('matched_at').matched_at
                stop = hits.latest('matched_at').matched_at
                duration = stop - start

                if duration.total_seconds() >= 30:
                    PlayLog.objects.create(
                        track_id=group['track_id'],
                        station_id=group['station_id'],
                        start_time=start,
                        stop_time=stop,
                        duration=duration
                    )
                    print(f"✅ Logged valid play: {duration.total_seconds()}s")

                hits.delete()
