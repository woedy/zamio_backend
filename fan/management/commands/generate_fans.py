from decimal import Decimal
import random
from bank_account.models import BankAccount
from faker import Faker
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
from django.contrib.auth import get_user_model

from fan.models import Fan
User = get_user_model()


fake = Faker()

REGIONS = ["Greater Accra", "Ashanti", "Northern", "Western", "Eastern", "Central"]
COUNTRIES = ["Ghana"]

class Command(BaseCommand):
    help = 'Generate random Fan profiles with linked new Users'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10, help='Number of fans to generate')

    def handle(self, *args, **options):
        count = options['count']

        created_fans = []

        for _ in range(count):
            # Create a new user for each Fan
            email = fake.unique.email()
            username = fake.unique.user_name()
            user = User.objects.create(
                email=email,
                username=username,
                user_id=f"USR-{get_random_string(8).upper()}",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                user_type="Fan",
                country=random.choice(COUNTRIES),
                phone=fake.phone_number(),
                email_verified=True,
                is_active=True,
                verified=random.choice([True, False]),
            )

            # Create Fan linked to this User
            fan = Fan.objects.create(
                user=user,
                username=username,
                dob=fake.date_of_birth(minimum_age=15, maximum_age=80),
                phone=user.phone,
                region=random.choice(REGIONS),
                country=user.country,
                location_name=fake.city(),
                lat=round(random.uniform(-1.0, 1.0), 8),
                lng=round(random.uniform(-1.0, 1.0), 8),
                bio=fake.text(max_nb_chars=200),
                active=True,
                is_archived=False,
            )

            created_fans.append(fan)
            # Create or fetch artist's bank account
            bank_account, _ = BankAccount.objects.get_or_create(user=user, defaults={
            "balance": Decimal('0.00'),
            "currency": "Ghc"
            })

             #Update Bank account
            bank_account.balance = Decimal(round(random.uniform(1000.00, 50000.00), 2))
            bank_account.save()

            self.stdout.write(self.style.SUCCESS(f"Created Fan: {fan.username} linked to new User ID {user.user_id}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Successfully created {len(created_fans)} Fan profiles with linked Users."))

#python manage.py generate_fans --count=20
