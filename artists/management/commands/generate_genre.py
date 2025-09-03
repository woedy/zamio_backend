from decimal import Decimal
import random
from artists.models import Album, Artist, Contributor, Fingerprint, Genre, Track, TrackFeedback
from bank_account.models import BankAccount
from faker import Faker
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
from datetime import timedelta, datetime, timedelta as dt
from django.db import transaction

from django.contrib.auth import get_user_model

from fan.models import Fan
User = get_user_model()

fake = Faker()


GENRES = ["HipHop", "Gosple", "Jazz", "Afro Pop", "Rock", "HighLife"]
COLORS = ["#007256", "#AA00BA", "#E30090", "#F0EC04", "#10B981", "#313D4A"]

class Command(BaseCommand):
    help = 'Generate random Artist profiles with linked Users, Albums, Tracks, Contributors, Feedbacks, and Fingerprints'


    def handle(self, *args, **options):
        for genre in GENRES:
            new_genre = Genre.objects.create(
                name=genre, 
                color=random.choice(COLORS),
                )

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully created Genres created"
        ))
#python manage.py generate_genre