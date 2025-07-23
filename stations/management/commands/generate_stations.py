from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
from django.utils import timezone
from bank_account.models import BankAccount
from faker import Faker
from django.contrib.auth import get_user_model

import random

from stations.models import ProgramStaff, Station, StationProgram, StationStreamLink


User = get_user_model()



fake = Faker()

REGIONS = ["Greater Accra", "Ashanti", "Northern", "Western", "Eastern", "Central"]
COUNTRIES = ["Ghana"]
ROLES = ["Producer", "Presenter", "Dj"]

class Command(BaseCommand):
    help = 'Generate random stations with users, programs, links and staff'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=5, help='Number of stations to generate')

    def handle(self, *args, **options):
        count = options['count']
        created_stations = []

        for _ in range(count):
            # Create user for the station
            email = fake.unique.email()
            username = fake.unique.user_name()
            user = User.objects.create(
                email=email,
                username=username,
                user_id=f"USR-{get_random_string(8).upper()}",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                user_type="Station",
                phone=fake.phone_number(),
                email_verified=True,
                is_active=True,
                verified=True,
            )

            region = random.choice(REGIONS)
            country = "Ghana"
            station_name = f"{fake.city()} FM"
            

            # Create the Station
            station = Station.objects.create(
                user=user,
                name=station_name,
                station_id=f"ST-{get_random_string(10).upper()}",
                phone=user.phone,
                region=region,
                country=country,
                location_name=fake.address(),
                lat=round(random.uniform(5.0, 11.0), 8),
                lng=round(random.uniform(-2.0, 1.0), 8),
                about=fake.paragraph(nb_sentences=3),
                avg_detection_confidence=round(random.uniform(85.0, 99.9), 2),
                active=True,
            )


            balance = round(random.uniform(1000.00, 50000.00), 2)

            # Create or fetch artist's bank account
            bank_account, _ = BankAccount.objects.get_or_create(user=user, defaults={
                "balance": Decimal('0.00'),
                "currency": "Ghc"
            })

            bank_account.deposit(
                amount=Decimal(balance),
                description=f"Initial Deposit"
            )

            # Add 1–3 Station Programs
            for _ in range(random.randint(1, 3)):
                program = StationProgram.objects.create(
                    station=station,
                    program_name=fake.catch_phrase(),
                    description=fake.text(max_nb_chars=200),
                    active=True,
                )

                # Add 1–2 staff per program
                for _ in range(random.randint(1, 2)):
                    ProgramStaff.objects.create(
                        station_program=program,
                        name=fake.name(),
                        role=random.choice(ROLES),
                        active=True,
                    )

            # Add 1–2 streaming links
            for _ in range(random.randint(1, 2)):
                StationStreamLink.objects.create(
                    station=station,
                    link=f"https://stream.{station.name.replace(' ', '').lower()}.com/live",
                    active=True,
                )

            created_stations.append(station)

        self.stdout.write(self.style.SUCCESS(f"✅ Created {len(created_stations)} stations with users, programs, and links."))



#python manage.py generate_stations --count=10
