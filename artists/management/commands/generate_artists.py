from decimal import Decimal
import random
from artists.models import Album, Artist, Contributor, Fingerprint, Genre, Track
from bank_account.models import BankAccount
from faker import Faker
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
from datetime import timedelta, datetime, timedelta as dt
from django.db import transaction

from django.contrib.auth import get_user_model

User = get_user_model()

fake = Faker()


REGIONS = ["Greater Accra", "Ashanti", "Northern", "Western", "Eastern", "Central"]
COUNTRIES = ["Ghana"]
ROLES = ['Composer', 'Producer', 'Writer', 'Featured Artist', 'Mixer', 'Engineer']

class Command(BaseCommand):
    help = 'Generate random Artist profiles with linked Users, Albums, Tracks, Contributors, and Fingerprints (no Fans)'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10, help='Number of artists to generate')

    def random_date(self, start_year=2000, end_year=2024):
        """Generate a random date between start_year-01-01 and end_year-12-31"""
        start = datetime(year=start_year, month=1, day=1)
        end = datetime(year=end_year, month=12, day=31)
        delta = end - start
        random_days = random.randint(0, delta.days)
        return start + timedelta(days=random_days)

    def handle(self, *args, **options):
        count = options['count']

        genres = list(Genre.objects.all())
        if not genres:
            self.stdout.write(self.style.ERROR("No genres found in the database. Please add genres first."))
            return

        created_artists = []

        with transaction.atomic():
            for _ in range(count):
                # Create User
                email = fake.unique.email()
                username = fake.unique.user_name()
                user = User.objects.create(
                    email=email,
                    username=username,
                    user_id=f"USR-{get_random_string(8).upper()}",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    user_type="Artist",
                    country=random.choice(COUNTRIES),
                    phone=fake.phone_number(),
                    email_verified=True,
                    is_active=True,
                    verified=random.choice([True, False]),
                )


                # Create or fetch artist's bank account
                bank_account, _ = BankAccount.objects.get_or_create(user=user, defaults={
                "balance": Decimal('0.00'),
                "currency": "Ghc"
                })



                # Create Artist
                stage_name = fake.unique.name()
                artist = Artist.objects.create(
                    user=user,
                    artist_id=f"ART-{get_random_string(10).upper()}",
                    stage_name=stage_name,
                    bio=fake.text(max_nb_chars=200),
                    total_earnings=str(round(random.uniform(1000.00, 50000.00), 2)),
                    region=random.choice(REGIONS),
                    country=user.country,
                    location_name=fake.city(),
                    lat=round(random.uniform(-1.0, 1.0), 8),
                    lng=round(random.uniform(-1.0, 1.0), 8),
                    contact_email=user.email,
                    spotify_url=f"https://open.spotify.com/artist/{get_random_string(22)}",
                    shazam_url=f"https://www.shazam.com/artist/{get_random_string(10)}",
                    instagram=f"https://instagram.com/{username}",
                    twitter=f"https://twitter.com/{username}",
                    website=f"https://{username}.com",
                    verified=random.choice([True, False]),
                    active=True,
                )
                self.stdout.write(self.style.SUCCESS(f"Created Artist: {artist.stage_name}"))

                #Update Bank account
                bank_account.balance = Decimal(artist.total_earnings)
                bank_account.save()


                # Generate random number of albums (1-3)
                album_count = random.randint(1, 3)
                albums = []
                for _ in range(album_count):
                    genre = random.choice(genres)
                    album_release_date = self.random_date()
                    albums.append(Album(
                        #album_id=f"ALB-{get_random_string(10).upper()}",
                        artist=artist,
                        title=fake.sentence(nb_words=3).rstrip('.'),
                        #genre=genre,
                        release_date=album_release_date,
                    ))
                Album.objects.bulk_create(albums)



                albums = Album.objects.filter(artist=artist)

                # Generate Tracks per Album (2-5 each)
                for album in albums:
                    track_count = random.randint(2, 5)
                    track_objs = []
                    for _ in range(track_count):
                        track_release_date = self.random_date(
                            start_year=album.release_date.year,
                            end_year=2024
                        )
                        track_objs.append(Track(
                            track_id=f"TR-{get_random_string(8).upper()}",
                            artist=artist,
                            album=album,
                            title=fake.sentence(nb_words=3).rstrip('.'),
                            genre=genre,
                            duration=timedelta(seconds=random.randint(120, 360)),
                            release_date=track_release_date,
                        ))
                    Track.objects.bulk_create(track_objs)

                    tracks = Track.objects.filter(album=album)

                    for track in tracks:
                        # Contributors
                        contributor_count = random.randint(1, 4)
                        contributors = []
                        percent_splits = []
                        for i in range(contributor_count):
                            role = random.choice(ROLES)
                            if i == contributor_count - 1:
                                percent_split = 100 - sum(percent_splits)
                            else:
                                remaining = 100 - sum(percent_splits)
                                percent_split = round(random.uniform(5, remaining / (contributor_count - i)), 2)
                            percent_splits.append(percent_split)

                        contributors.append(Contributor(
                                track=track,
                                user=user,
                                role=role,
                                percent_split=percent_split,
                                active=True,
                                is_archived=False,
                            ))
                        Contributor.objects.bulk_create(contributors)
                        self.stdout.write(f"  Created {contributor_count} contributors for track '{track.title}'")

                        # Skipping TrackFeedback generation (no Fan dependency in simulation)

                        # Fingerprints
                        fingerprint_count = random.randint(5, 10)
                        fingerprints = []
                        for _ in range(fingerprint_count):
                            hash_str = get_random_string(length=20)
                            offset = random.randint(0, 300)
                            fingerprints.append(Fingerprint(
                                track=track,
                                hash=hash_str,
                                offset=offset,
                            ))
                        Fingerprint.objects.bulk_create(fingerprints)
                        self.stdout.write(f"  Created {fingerprint_count} fingerprints for track '{track.title}'")

                created_artists.append(artist)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully created {len(created_artists)} artists with albums, tracks, contributors, and fingerprints."
        ))
#python manage.py generate_artists --count=20

