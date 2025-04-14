# management/commands/fingerprint_tracks.py
from django.core.management.base import BaseCommand
from artists.models import Track
from core.settings import DEJAVU_CONFIG
from dejavu import Dejavu

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        djv = Dejavu(DEJAVU_CONFIG)

        for track in Track.objects.all():
            song_name = f"{track.id}__{track.title}__{track.artist}"
            djv.fingerprint_file(track.file_path, song_name=song_name)
            self.stdout.write(f"✅ Fingerprinted: {track.title}")
