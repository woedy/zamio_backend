from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from datetime import timedelta, datetime
from decimal import Decimal
import random

from artists.models import Artist, Album, Track, Genre
from stations.models import Station
from music_monitor.models import MatchCache

# Reuse processing pipeline from the existing simulator
from music_monitor.management.commands.simulate__historical_streams_and_payments import Command as ProcessCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Generate 1-year historical plays and payouts for a single artist across 4 stations (2 albums, 14 tracks)."

    def add_arguments(self, parser):
        parser.add_argument('--artist-email', type=str, default='artist.sim@example.com')
        parser.add_argument('--first-name', type=str, default='Sim')
        parser.add_argument('--last-name', type=str, default='Artist')
        parser.add_argument('--stage-name', type=str, default='Simulated Star')
        parser.add_argument('--start-date', type=str, help='YYYY-MM-DD start date; defaults to 365 days ago')
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--stations', type=int, default=4)
        parser.add_argument('--clear-existing-for-artist', action='store_true')

    def handle(self, *args, **opts):
        random.seed(opts['seed'])

        artist_user, artist, albums, tracks = self._ensure_artist_catalog(
            email=opts['artist_email'],
            first_name=opts['first_name'],
            last_name=opts['last_name'],
            stage_name=opts['stage_name'],
        )
        stations = self._ensure_stations(opts['stations'])

        if opts['clear_existing_for_artist']:
            self._clear_existing_for_tracks([t.id for t in tracks])

        # Determine date range (~1 year)
        if opts.get('start_date'):
            start_date = timezone.make_aware(datetime.strptime(opts['start_date'], '%Y-%m-%d'))
        else:
            start_date = timezone.now() - timedelta(days=365)
        total_days = 365

        self.stdout.write(f"🎼 Simulating ~{total_days} days from {start_date.date()} for artist {artist.stage_name}")
        created = self._simulate_match_caches_for_tracks(tracks, stations, start_date, total_days)
        self.stdout.write(self.style.SUCCESS(f"✅ Created {created:,} MatchCache entries"))

        # Process matches into playlogs + payouts
        self.stdout.write("🔄 Processing matches into playlogs and payments...")
        proc = ProcessCommand()
        proc.stdout = self.stdout  # reuse output stream
        proc.process_matches_to_playlogs_bulk()
        self.stdout.write(self.style.SUCCESS("🎉 Completed processing for artist year history"))

    def _ensure_artist_catalog(self, email, first_name, last_name, stage_name):
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'user_type': 'Artist',
                'email_verified': True,
                'is_active': True,
            }
        )
        if not user.user_type:
            user.user_type = 'Artist'
            user.email_verified = True
            user.is_active = True
            user.save()

        artist, _ = Artist.objects.get_or_create(user=user, defaults={'stage_name': stage_name})
        if not artist.stage_name:
            artist.stage_name = stage_name
            artist.save()

        # Ensure a Genre exists to attach to tracks
        genre = Genre.objects.first()
        if not genre:
            genre = Genre.objects.create(name='Pop', color='#FF00AA')

        # Ensure two albums with 7 tracks each (14 total)
        albums = []
        tracks = list(Track.objects.filter(artist=artist))
        if len(tracks) < 14:
            albums = [
                Album.objects.create(title=f"{stage_name} Album 1", artist=artist),
                Album.objects.create(title=f"{stage_name} Album 2", artist=artist),
            ]
            # Create 14 tracks with minimal required fields and a tiny dummy audio file
            for i in range(14):
                album = albums[0] if i < 7 else albums[1]
                title = f"{stage_name} Track {i+1}"
                t = Track(
                    title=title,
                    artist=artist,
                    album=album,
                    genre=genre,
                    publisher_id=None,
                )
                # Attach a tiny dummy MP3-like file content
                t.audio_file.save(f"{title.replace(' ', '_').lower()}.mp3", ContentFile(b"ID3"), save=False)
                t.save()
            tracks = list(Track.objects.filter(artist=artist))

        # If albums list is empty because tracks already existed, fetch distinct albums
        if not albums:
            albums = list(Album.objects.filter(artist=artist)[:2])

        return user, artist, albums, tracks

    def _ensure_stations(self, count):
        stations = list(Station.objects.all()[:count])
        needed = count - len(stations)
        for i in range(max(0, needed)):
            email = f"station.sim{i+1}@example.com"
            su, _ = User.objects.get_or_create(email=email, defaults={
                'first_name': 'Station',
                'last_name': f"Sim{i+1}",
                'user_type': 'Station',
                'email_verified': True,
                'is_active': True,
            })
            st = Station.objects.create(user=su, name=f"Sim Station {i+1}")
            stations.append(st)
        return stations[:count]

    def _clear_existing_for_tracks(self, track_ids):
        from music_monitor.models import PlayLog, FailedPlayLog
        from bank_account.models import Transaction
        # Narrow deletes to only these tracks
        MatchCache.objects.filter(track_id__in=track_ids).delete()
        PlayLog.objects.filter(track_id__in=track_ids).delete()
        FailedPlayLog.objects.filter(track_id__in=track_ids).delete()
        # Transactions: best-effort based on memo or track linkage if modeled; otherwise skip
        Transaction.objects.all().delete()

    def _simulate_match_caches_for_tracks(self, tracks, stations, start_date, total_days):
        created = 0
        batch = []
        batch_size = 2000
        tz_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Popularity weights: simple equal distribution with slight variation
        weights = {t.id: random.uniform(0.8, 1.2) for t in tracks}
        total_w = sum(weights.values())

        for day in range(total_days):
            day_start = tz_start + timedelta(days=day)
            # Per-station plays per day (adjustable)
            plays_per_station = random.randint(40, 70)
            for station in stations:
                current = day_start
                for _ in range(plays_per_station):
                    # pick track weighted
                    r = random.uniform(0, total_w)
                    cum = 0
                    picked = tracks[0]
                    for t in tracks:
                        cum += weights[t.id]
                        if r <= cum:
                            picked = t
                            break
                    # 3-5 matches per play across the play window
                    duration = random.randint(150, 300)  # 2.5 to 5 minutes
                    num_matches = random.randint(3, 5)
                    # spread matches across duration
                    for j in range(num_matches):
                        offset = int((duration / num_matches) * j + random.randint(0, 15))
                        matched_at = current + timedelta(seconds=offset)
                        batch.append(MatchCache(
                            track=picked,
                            station=station,
                            station_program=None,
                            matched_at=matched_at,
                            avg_confidence_score=random.uniform(75, 95),
                            processed=False,
                        ))
                        if len(batch) >= batch_size:
                            MatchCache.objects.bulk_create(batch, batch_size=batch_size)
                            created += len(batch)
                            batch = []
                    # advance time to next play within the hour-ish window
                    current += timedelta(minutes=random.randint(5, 10))

        if batch:
            MatchCache.objects.bulk_create(batch, batch_size=batch_size)
            created += len(batch)

        return created

# python manage.py simulate_artist_year_history --artist-email you@example.com --stage-name "Your Artist"