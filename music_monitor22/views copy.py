import os, uuid
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.timezone import now
from .models import MatchCache, Track

@api_view(['POST'])
def process_audio_snippet(request):
    """
    Receives 10s audio snippet from Flutter, fingerprints it, and saves match.
    """
    station_id = request.data.get("station_id")
    timestamp = request.data.get("timestamp", now())
    audio_file = request.FILES['audio_file']

    # Save temp file
    tmp_path = f"/tmp/snippet_{uuid.uuid4()}.wav"
    with open(tmp_path, 'wb+') as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    # Fingerprint and match
    from .fingerprint import match_audio
    result = match_audio(tmp_path)

    os.remove(tmp_path)

    if result:
        MatchCache.objects.create(
            track_id=result["track_id"],
            station_id=station_id,
            matched_at=timestamp
        )
        return Response({"matched": True, "track_id": result["track_id"]})
    else:
        return Response({"matched": False})
    






import os
import tempfile
import datetime
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Track, PlayLog, Station
from .fingerprint import identify_audio
from pydub import AudioSegment




# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import MatchCache, Track, Station
from .fingerprint import identify_audio
from pydub import AudioSegment
from django.utils.timezone import now
import tempfile, os

# Memory buffer (station_id: [AudioSegment, ...])
chunk_buffers = {}

@api_view(['POST'])
def audio_snippet(request):
    audio_file = request.FILES.get("audio_file")
    station_id = int(request.POST.get("station_id", 0))

    if not audio_file or not station_id:
        return Response({"error": "Missing data"}, status=400)

    # Save uploaded audio to temp file (regardless of format: .aac, .opus, .webm)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp:
        temp.write(audio_file.read())
        audio_path = temp.name

    try:
        # 🔥 Auto-detect and load any format (aac, opus, etc.)
        chunk = AudioSegment.from_file(audio_path)

        # Buffering chunks for station
        if station_id not in chunk_buffers:
            chunk_buffers[station_id] = []

        chunk_buffers[station_id].append(chunk)

        # Keep only last 3 chunks
        if len(chunk_buffers[station_id]) > 3:
            chunk_buffers[station_id].pop(0)

        # Stitch chunks together
        stitched = sum(chunk_buffers[station_id], AudioSegment.silent(duration=0))

        # Export stitched audio to temp WAV for fingerprinting
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as stitch_file:
            stitched.export(stitch_file.name, format="wav")
            stitched_path = stitch_file.name

        # Identify using fingerprinting
        match = identify_audio(stitched_path)

    finally:
        # Cleanup
        os.remove(audio_path)
        if 'stitched_path' in locals():
            os.remove(stitched_path)

    if match:
        track = Track.objects.get(id=match["track_id"])
        MatchCache.objects.create(track=track, station_id=station_id)
        return Response({"matched": True, "track": track.title})

    return Response({"matched": False})


###################



# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import PlayLog, Track, Artist, Station
from .serializers import PlayLogSerializer, ArtistSerializer, StationSerializer

@api_view(['GET'])
def recent_plays(request):
    plays = PlayLog.objects.order_by('-start_time')[:20]
    serializer = PlayLogSerializer(plays, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def play_count_per_artist(request):
    from django.db.models import Sum, Count
    data = (
        PlayLog.objects
        .values('track__artist__name')
        .annotate(total_plays=Count('id'), total_royalty=Sum('royalty_amount'))
        .order_by('-total_plays')
    )
    return Response(data)

@api_view(['GET'])
def stations_list(request):
    stations = Station.objects.all()
    serializer = StationSerializer(stations, many=True)
    return Response(serializer.data)




@api_view(['GET'])
def recent_logs(request):
    logs = PlayLog.objects.select_related("track", "station").order_by('-start_time')[:50]
    data = [{
        "track": log.track.title,
        "artist": log.track.artist,
        "station": log.station.name,
        "start_time": log.start_time,
        "duration": log.duration.total_seconds(),
        "royalty": float(log.royalty_amount)
    } for log in logs]

    return Response(data)
