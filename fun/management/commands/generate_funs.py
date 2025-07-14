import random
from faker import Faker
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
from django.contrib.auth import get_user_model

from fun.models import Fun
User = get_user_model()


fake = Faker()

REGIONS = ["Greater Accra", "Ashanti", "Northern", "Western", "Eastern", "Central"]
COUNTRIES = ["Ghana"]

class Command(BaseCommand):
    help = 'Generate random Fun profiles with linked new Users'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10, help='Number of funs to generate')

    def handle(self, *args, **options):
        count = options['count']

        created_funs = []

        for _ in range(count):
            # Create a new user for each Fun
            email = fake.unique.email()
            username = fake.unique.user_name()
            user = User.objects.create(
                email=email,
                username=username,
                user_id=f"USR-{get_random_string(8).upper()}",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                user_type="Fun",
                country=random.choice(COUNTRIES),
                phone=fake.phone_number(),
                email_verified=True,
                is_active=True,
                verified=random.choice([True, False]),
            )

            # Create Fun linked to this User
            fun = Fun.objects.create(
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

            created_funs.append(fun)
            self.stdout.write(self.style.SUCCESS(f"Created Fun: {fun.username} linked to new User ID {user.user_id}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Successfully created {len(created_funs)} Fun profiles with linked Users."))

#python manage.py generate_funs --count=20
