from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
import random

from artists.models import Artist, Track
from music_monitor.models import PlayLog
from stations.models import Station, StationProgram


SOURCE_TYPE = ['radio', 'streaming', 'manual']
DISPUTE_STATUSES = ['Pending', 'Resolved', 'Rejected', 'Approved', None]


class Command(BaseCommand):
    help = 'Generate random PlayLog records for testing'

    def add_arguments(self, parser):
        parser.add_argument('--artist_id', type=str, required=True)
        parser.add_argument('--track_id', type=str, required=True)
        parser.add_argument('--station_id', type=str, required=True)
        parser.add_argument('--count', type=int, default=100)
        parser.add_argument('--start_date', type=str, help="YYYY-MM-DD")
        parser.add_argument('--end_date', type=str, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        artist_id = options['artist_id']
        track_id = options['track_id']
        station_id = options['station_id']
        count = options['count']

        start_date_str = options.get('start_date')
        end_date_str = options.get('end_date')

        try:
            artist = Artist.objects.get(artist_id=artist_id)
            track = Track.objects.get(track_id=track_id, artist=artist)
            station = Station.objects.get(station_id=station_id)
        except Artist.DoesNotExist:
            self.stderr.write("Artist not found.")
            return
        except Track.DoesNotExist:
            self.stderr.write("Track not found.")
            return
        except Station.DoesNotExist:
            self.stderr.write("Station not found.")
            return

        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()

        if start_date_str:
            start_date = timezone.make_aware(datetime.strptime(start_date_str, "%Y-%m-%d"))
        if end_date_str:
            end_date = timezone.make_aware(datetime.strptime(end_date_str, "%Y-%m-%d"))

        programs = StationProgram.objects.filter(station=station)
        created_logs = []

        self.stdout.write(f"Generating {count} PlayLogs from {start_date.date()} to {end_date.date()}")

        with transaction.atomic():
            for _ in range(count):
                # Random time within date range
                played_at = start_date + timedelta(
                    seconds=random.randint(0, int((end_date - start_date).total_seconds()))
                )

                duration_seconds = random.randint(120, 300)
                duration = timedelta(seconds=duration_seconds)
                start_time = played_at
                stop_time = start_time + duration

                playlog = PlayLog(
                    track=track,
                    station=station,
                    station_program=random.choice(programs) if programs else None,
                    source=random.choice(SOURCE_TYPE),
                    played_at=played_at,
                    start_time=start_time,
                    stop_time=stop_time,
                    duration=duration,
                    royalty_amount=round(random.uniform(0.10, 1.00), 2),
                    avg_confidence_score=round(random.uniform(85, 100), 2),
                    claimed=random.choice([True, False]),
                    flagged=random.choice([False, False, False, True]),  # Mostly clean
                    dispute_status=random.choice(DISPUTE_STATUSES),
                    disput_comments=None,
                    active=True
                )
                created_logs.append(playlog)

            PlayLog.objects.bulk_create(created_logs)

        self.stdout.write(self.style.SUCCESS(f"Successfully created {len(created_logs)} PlayLog records."))








# python manage.py generate_playlogs \
#   --artist_id=AR-0P5EFYIS-ST \
#   --track_id=TR-2ID0LE-CK \
#   --station_id=ST-Q58GWOZKW-ON \
#   --count=200 \
#   --start_date=2025-07-01 \
#   --end_date=2025-07-14


#python manage.py generate_playlogs --artist_id=AR-0P5EFYIS-ST --track_id=TR-2ID0LE-CK --station_id=ST-Q58GWOZKW-ON --count=200 --start_date=2025-07-01 --end_date=2025-07-14
