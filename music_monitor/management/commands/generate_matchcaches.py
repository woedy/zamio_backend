from django.core.management.base import BaseCommand
from artists.models import Track
from faker import Faker
import random

from music_monitor.models import MatchCache
from stations.models import Station, StationProgram


fake = Faker()

class Command(BaseCommand):
    help = 'Generate random MatchCache entries from streamed tracks'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=20, help='Number of match caches to create')

    def handle(self, *args, **options):
        count = options['count']
        tracks = list(Track.objects.all())
        stations = list(Station.objects.all())
        programs = list(StationProgram.objects.all())

        if not tracks or not stations:
            self.stdout.write(self.style.ERROR("🚫 No tracks or stations available."))
            return

        created = 0
        for _ in range(count):
            track = random.choice(tracks)
            station = random.choice(stations)

            # Prevent duplicate matches for same track/station
            if MatchCache.objects.filter(track=track, station=station, processed=False).exists():
                continue

            MatchCache.objects.create(
                track=track,
                station=station,
                station_program=random.choice(programs) if programs and random.choice([True, False]) else None,
                avg_confidence_score=round(random.uniform(55.0, 99.9), 2),
                processed=False,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Created {created} MatchCache entries."))



#python manage.py generate_matchcaches --count=20
