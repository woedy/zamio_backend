# streamer/tasks.py
from celery import shared_task
from streamer.models import AudioMatch, StreamSource
from your_fingerprint_lib import fingerprint, match_fingerprint
import os

@shared_task
def match_audio_clip(audio_path, station_id):
    try:
        print(f"[TASK] Matching clip: {audio_path}")
        fp = fingerprint(audio_path)
        result = match_fingerprint(fp)

        if result:
            station = StreamSource.objects.get(id=station_id)
            AudioMatch.objects.create(
                track_title=result['title'],
                artist=result['artist'],
                confidence=result['confidence'],
                station=station,
                clip_file=audio_path
            )
            print(f"✓ Match found: {result['title']} by {result['artist']}")
        else:
            print("No match.")
    finally:
        # Clean up temp file
        if os.path.exists(audio_path):
            os.remove(audio_path)
