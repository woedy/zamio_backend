import os, tempfile
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from dejavu import Dejavu
from dejavu.recognize import FileRecognizer
from .models import Track, PlayLog, Station
from dejavu_config import config

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_clip(request):
    audio_file = request.FILES.get('file')
    station_id = request.data.get('station_id')

    if not audio_file:
        return Response({"error": "No file provided"}, status=400)

    # Save audio temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        for chunk in audio_file.chunks():
            temp_audio.write(chunk)
        temp_path = temp_audio.name

    # Initialize Dejavu
    djv = Dejavu(config)

    try:
        result = djv.recognize(FileRecognizer, temp_path)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    finally:
        os.remove(temp_path)

    if result is None or result.get('song_name') is None:
        return Response({"matched": False, "message": "No match found"})

    # Find matched track in DB
    matched_title = result['song_name']
    try:
        track = Track.objects.get(title__iexact=matched_title)
        station = Station.objects.get(id=station_id)
        PlayLog.objects.create(track=track, station=station)
    except Track.DoesNotExist:
        return Response({"matched": False, "message": "Track not found in DB"})
    except Station.DoesNotExist:
        return Response({"error": "Invalid station ID"}, status=400)

    return Response({
        "matched": True,
        "title": track.title,
        "artist": track.artist.name,
        "timestamp": result['offset_seconds'],
    })


# Assume we pay $0.10 per minute of play for each song
def calculate_royalty(playlog):
    rate_per_minute = 0.10
    duration_in_minutes = playlog.duration.total_seconds() / 60
    return rate_per_minute * duration_in_minutes





def calculate_royalty(self, duration):
    rate_per_minute = 0.10  # Or dynamic
    minutes = duration.total_seconds() / 60
    return round(rate_per_minute * minutes, 2)






from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now, timedelta

from .models import MatchCache, PlayLog, Track, Station

@api_view(['POST'])
def receive_match(request):
    """
    Receives match data from the audio analyzer
    """
    track_id = request.data.get("track_id")
    station_id = request.data.get("station_id")
    match_time = request.data.get("match_time", now())

    if isinstance(match_time, str):
        match_time = parse_datetime(match_time)

    MatchCache.objects.create(
        track_id=track_id,
        station_id=station_id,
        matched_at=match_time
    )

    return Response({"message": "Match received"})







#################

@api_view(['POST'])
def process_audio_snippet(request):
    station_id = request.data.get("station_id")
    timestamp = request.data.get("timestamp", now())
    audio_file = request.FILES['audio_file']

    # Save file temporarily
    tmp_path = f"/tmp/snippet_{uuid.uuid4()}.wav"
    with open(tmp_path, 'wb+') as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    # 1. Fingerprint + match (using Dejavu or your engine)
    matched = fingerprint_and_match(tmp_path)

    # 2. If match found → log to MatchCache
    if matched:
        MatchCache.objects.create(
            track_id=matched["track_id"],
            station_id=station_id,
            matched_at=timestamp
        )

    # Clean up
    os.remove(tmp_path)

    return Response({"matched": bool(matched)})



def fingerprint_and_match(filepath):
    from dejavu import Dejavu
    from dejavu.recognize import FileRecognizer
    from dejavu_config import config  # Your DB config for fingerprinting

    djv = Dejavu(config)
    result = djv.recognize(FileRecognizer, filepath)

    if result and result['confidence'] > 5:
        return {
            "track_id": get_django_track_id(result['song_name']),
            "confidence": result['confidence'],
        }

    return None
