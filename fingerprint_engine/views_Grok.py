from celery import shared_task
import librosa
from django.core.cache import cache
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response



@api_view(['POST'])
@parser_classes([MultiPartParser])
def detect_audio_match(request):
    audio_file = request.FILES.get('audio_file')
    if not audio_file:
        return Response({"error": "No audio file uploaded"}, status=400)

    # Check cache
    cache_key = hashlib.sha256(audio_file.read()).hexdigest()
    cached_result = cache.get(cache_key)
    if cached_result:
        return Response(cached_result)

    # Process audio
    with NamedTemporaryFile(delete=False) as temp:
        for chunk in audio_file.chunks():
            temp.write(chunk)
        original_temp_path = temp.name

    wav_path = convert_to_wav_ffmpeg(original_temp_path)
    if not wav_path:
        os.remove(original_temp_path)
        return Response({"error": "Failed to convert audio to WAV"}, status=500)

    try:
        query_fingerprints = extract_fingerprints(wav_path)
        if not query_fingerprints:
            return Response({"match": False, "reason": "No fingerprints extracted"})

        query_hashes = [h for h, _ in query_fingerprints]
        db_fps = []
        for chunk in chunk_list(query_hashes, 1000):
            db_fps.extend(Fingerprint.objects.filter(hash__in=chunk))

        # Matching logic (unchanged)
        # ...

        result = {
            "match": True,
            "song_id": matched_song.id,
            # ...
        }
        cache.set(cache_key, result, timeout=3600)
        return Response(result)
    except Exception as e:
        logger.exception("Matching error")
        return Response({"error": "Internal server error"}, status=500)
    finally:
        os.remove(original_temp_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)