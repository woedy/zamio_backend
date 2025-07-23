import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from artists.models import Artist
from notifications.models import Notification
from stations.models import Station  # Adjust import based on your structure


NOTIFICATION_TYPES = ["summary", "update", "compliance", "info", "warning"]
TITLES = [
    "Weekly Summary Report", "Compliance Alert", "Platform Update",
    "New Station Detected", "Royalty Payment Processed", "Export Reminder"
]
MESSAGES = [
    "45 songs detected this week on XYZ FM.",
    "Your monthly compliance report is pending.",
    "We have added new features to the dashboard.",
    "Station YFM detected 12 of your tracks today.",
    "Your royalty payment has been sent via MTN MoMo.",
    "Please export your June report before deadline."
]


class Command(BaseCommand):
    help = 'Generate random notifications for a given artist or station'

    def add_arguments(self, parser):
        parser.add_argument('--artist_id', type=str, help='Artist ID')
        parser.add_argument('--station_id', type=str, help='Station ID')
        parser.add_argument('--count', type=int, default=10, help='Number of notifications to generate')

    def handle(self, *args, **options):
        artist_id = options['artist_id']
        station_id = options['station_id']
        count = options['count']

        if not artist_id and not station_id:
            self.stdout.write(self.style.ERROR("You must provide either --artist_id or --station_id"))
            return

        user = None
        if artist_id:
            try:
                artist = Artist.objects.get(artist_id=artist_id)
                user = artist.user
                self.stdout.write(self.style.SUCCESS(f"Found artist: {artist.stage_name or artist.name}"))
            except Artist.DoesNotExist:
                self.stdout.write(self.style.ERROR("Artist not found"))
                return

        elif station_id:
            try:
                station = Station.objects.get(station_id=station_id)
                user = station.user
                self.stdout.write(self.style.SUCCESS(f"Found station: {station.name}"))
            except Station.DoesNotExist:
                self.stdout.write(self.style.ERROR("Station not found"))
                return

        notifications = []
        for _ in range(count):
            notification = Notification(
                user=user,
                title=random.choice(TITLES),
                message=random.choice(MESSAGES),
                type=random.choice(NOTIFICATION_TYPES),
                created_at=timezone.now() - timedelta(days=random.randint(0, 30)),
                is_archived=False,
                read=random.choice([True, False])
            )
            notifications.append(notification)

        Notification.objects.bulk_create(notifications)
        self.stdout.write(self.style.SUCCESS(f"{count} notifications created successfully!"))



#python manage.py generate_notifications --artist_id=ARTIST123 --count=15
