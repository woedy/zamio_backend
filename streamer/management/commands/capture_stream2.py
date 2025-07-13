# streamer/management/commands/capture_stream.py
from django.core.management.base import BaseCommand
from streamer.models import StreamSource
from streamer.services.streamer import capture_and_match_loop

class Command(BaseCommand):
    help = "Continuously captures and matches live streams"

    def handle(self, *args, **options):
        sources = StreamSource.objects.filter(is_active=True)
        for source in sources:
            capture_and_match_loop(source.stream_url, source.name)
