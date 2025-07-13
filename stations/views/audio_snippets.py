from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import MatchCache, Track, Station
from .fingerprint import identify_audio
from pydub import AudioSegment
from django.utils.timezone import now
import tempfile, os


# Memory buffer (station_id: [AudioSegment, ...])
chunk_buffers = {}


@api_view(["POST"])
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
        if "stitched_path" in locals():
            os.remove(stitched_path)

    if match:
        track = Track.objects.get(id=match["track_id"])
        MatchCache.objects.create(track=track, station_id=station_id)
        return Response({"matched": True, "track": track.title})

    return Response({"matched": False})
