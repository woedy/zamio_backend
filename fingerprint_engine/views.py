import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.storage import default_storage

from fingerprint_engine.tasks import (
    convert_to_wav_ffmpeg,
    extract_fingerprints,
    generate_fingerprints_for_song,
)


from .models import Song

from tempfile import NamedTemporaryFile
from django.http import JsonResponse
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from .models import Song, Fingerprint
from collections import Counter


@csrf_exempt  # Only for development — better to use CSRF token or API token in production
def upload_audio_api(request):
    if request.method == "POST":
        title = request.POST.get("title")
        audio_file = request.FILES.get("audio_file")

        if not title or not audio_file:
            return JsonResponse({"error": "Missing title or audio file."}, status=400)

        # Save the file
        song = Song.objects.create(title=title, audio_file=audio_file)

        # Trigger fingerprinting
        generate_fingerprints_for_song(song.id)

        # Respond with success
        return JsonResponse(
            {
                "message": "Audio uploaded and fingerprinting started.",
                "song": {
                    "id": song.id,
                    "title": song.title,
                    "file_url": song.audio_file.url,
                },
            }
        )

    return JsonResponse({"error": "Only POST method allowed."}, status=405)



import time

@api_view(['POST'])
@parser_classes([MultiPartParser])
def detect_audio_match(request):
    audio_file = request.FILES.get('audio_file')
    if not audio_file:
        return JsonResponse({"error": "No audio file uploaded"}, status=400)

    with NamedTemporaryFile(delete=False) as temp:
        for chunk in audio_file.chunks():
            temp.write(chunk)
        original_temp_path = temp.name

    # Step 1: Convert to proper WAV
    wav_path = convert_to_wav_ffmpeg(original_temp_path)

    if not wav_path:
        os.remove(original_temp_path)
        return JsonResponse({"error": "Failed to convert audio to WAV"}, status=500)

    try:
        t_start = time.time()
        query_fingerprints = extract_fingerprints(wav_path)
        t_fingerprint = time.time()

        if not query_fingerprints:
            return JsonResponse({"match": False, "reason": "No fingerprints extracted"})

        query_hashes = [h for h, _ in query_fingerprints]
        db_fps = Fingerprint.objects.filter(hash__in=query_hashes)

        if not db_fps.exists():
            return JsonResponse({"match": False, "reason": "No matching hashes in DB"})

        match_map = Counter()
        for fp in db_fps:
            for h, query_offset in query_fingerprints:
                if fp.hash == h:
                    offset_diff = fp.offset - query_offset
                    match_map[(fp.song_id, offset_diff)] += 1

        if not match_map:
            return JsonResponse({"match": False, "reason": "No offset alignment found"})

        (song_id, offset_diff), match_count = match_map.most_common(1)[0]
        matched_song = Song.objects.get(id=song_id)

        # Stats
        total_query_hashes = len(query_hashes)
        total_song_hashes = Fingerprint.objects.filter(song_id=song_id).count()

        input_confidence = (match_count / total_query_hashes) * 100
        db_confidence = (match_count / total_song_hashes) * 100 if total_song_hashes else 0

        # Tune your own thresholds here
        MIN_MATCH_COUNT = 50
        MIN_INPUT_CONF = 20.0  # % of query matched
        MIN_DB_CONF = 5.0      # % of song's fingerprints matched

        if match_count < MIN_MATCH_COUNT or input_confidence < MIN_INPUT_CONF or db_confidence < MIN_DB_CONF:
            return JsonResponse({
                "match": False,
                "reason": "Low confidence match",
                "hashes_matched": match_count,
                "input_confidence": round(input_confidence, 2),
                "db_confidence": round(db_confidence, 2)
            })

        t_end = time.time()

        return JsonResponse({
            "match": True,
            "song_id": matched_song.id,
            "song_name": matched_song.title,
            "offset": int(offset_diff),
            "offset_seconds": round(offset_diff * 0.32, 2),  # frame size to seconds approx
            "hashes_matched_in_input": match_count,
            "input_total_hashes": total_query_hashes,
            "fingerprinted_hashes_in_db": total_song_hashes,
            "input_confidence": round(input_confidence, 2),
            "fingerprinted_confidence": round(db_confidence, 2),
            "total_time": round(t_end - t_start, 2),
            "fingerprint_time": round(t_fingerprint - t_start, 2),
            "query_time": round(t_end - t_fingerprint, 2)
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    finally:
        os.remove(original_temp_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)