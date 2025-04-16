from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import hashlib
import logging
import os
import time
from tempfile import NamedTemporaryFile
from collections import Counter
from .models import Song, Fingerprint
from .tasks import generate_fingerprints_for_song, convert_to_wav_ffmpeg, extract_fingerprints

logger = logging.getLogger(__name__)

class DetectAudioMatchThrottle(UserRateThrottle):
    rate = '100/hour'  # Limit to 100 requests per hour per user

@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_audio_api(request):
    """
    Upload an audio file and queue fingerprinting asynchronously.
    
    Accepts multipart form data with 'title' and 'audio_file' fields.
    """
    try:
        title = request.POST.get("title")
        audio_file = request.FILES.get("audio_file")

        # Validate inputs
        if not title or not audio_file:
            return Response({"error": "Missing title or audio file."}, status=400)

        # Validate file extension and size
        validator = FileExtensionValidator(allowed_extensions=['mp3', 'wav'])
        validator(audio_file)
        max_size = 50 * 1024 * 1024  # 50 MB
        if audio_file.size > max_size:
            return Response({"error": "File size exceeds 50 MB."}, status=400)

        # Save the song
        song = Song.objects.create(title=title, audio_file=audio_file)
        
        # Queue fingerprinting task
        task = generate_fingerprints_for_song.delay(song.id)
        logger.info(f"Queued fingerprinting task {task.id} for song {song.id}: {song.title}")

        return Response({
            "message": "Audio uploaded and fingerprinting queued.",
            "song": {
                "id": song.id,
                "title": song.title,
                "file_url": song.audio_file.url,
            }
        })

    except ValidationError as e:
        logger.error(f"Invalid file upload: {e}")
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        logger.exception(f"Error uploading audio: {e}")
        return Response({"error": "Internal server error."}, status=500)

@api_view(['POST'])
@parser_classes([MultiPartParser])
@throttle_classes([DetectAudioMatchThrottle])
def detect_audio_match(request):
    """
    Detect if an uploaded audio clip matches a song in the database.
    
    Accepts multipart form data with an 'audio_file' field.
    """
    audio_file = request.FILES.get('audio_file')
    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=400)

    # Check cache
    audio_hash = hashlib.sha256(audio_file.read()).hexdigest()
    cached_result = cache.get(audio_hash)
    if cached_result:
        logger.info(f"Returning cached result for audio hash {audio_hash}")
        return Response(cached_result)
    audio_file.seek(0)  # Reset file pointer after hashing

    # Save audio to temporary file
    with NamedTemporaryFile(delete=False) as temp:
        for chunk in audio_file.chunks():
            temp.write(chunk)
        original_temp_path = temp.name

    try:
        # Convert to WAV
        wav_path = convert_to_wav_ffmpeg(original_temp_path)
        if not wav_path:
            return Response({"error": "Failed to convert audio to WAV."}, status=500)

        # Extract fingerprints
        t_start = time.time()
        query_fingerprints = extract_fingerprints(wav_path)
        t_fingerprint = time.time()

        if not query_fingerprints:
            return Response({"match": False, "reason": "No fingerprints extracted."}, status=200)

        # Batch query hashes
        query_hashes = [h for h, _ in query_fingerprints]
        db_fps = []
        batch_size = 1000
        for i in range(0, len(query_hashes), batch_size):
            db_fps.extend(Fingerprint.objects.filter(hash__in=query_hashes[i:i + batch_size]))

        if not db_fps:
            return Response({"match": False, "reason": "No matching hashes in database."}, status=200)

        # Match fingerprints
        match_map = Counter()
        for fp in db_fps:
            for h, query_offset in query_fingerprints:
                if fp.hash == h:
                    offset_diff = fp.offset - query_offset
                    match_map[(fp.song_id, offset_diff)] += 1

        if not match_map:
            return Response({"match": False, "reason": "No offset alignment found."}, status=200)

        (song_id, offset_diff), match_count = match_map.most_common(1)[0]
        
        # Fetch matched song
        try:
            matched_song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            logger.error(f"Song {song_id} not found")
            return Response({"error": "Matched song not found."}, status=500)

        # Calculate confidence
        total_query_hashes = len(query_hashes)
        total_song_hashes = Fingerprint.objects.filter(song_id=song_id).count()
        input_confidence = (match_count / total_query_hashes) * 100
        db_confidence = (match_count / total_song_hashes) * 100 if total_song_hashes else 0

        # Thresholds
        MIN_MATCH_COUNT = 50
        MIN_INPUT_CONF = 20.0  # % of query matched
        MIN_DB_CONF = 5.0      # % of song's fingerprints matched

        t_end = time.time()

        if match_count < MIN_MATCH_COUNT or input_confidence < MIN_INPUT_CONF or db_confidence < MIN_DB_CONF:
            result = {
                "match": False,
                "reason": "Low confidence match.",
                "hashes_matched": match_count,
                "input_confidence": round(input_confidence, 2),
                "db_confidence": round(db_confidence, 2)
            }
            cache.set(audio_hash, result, timeout=3600)  # Cache for 1 hour
            return Response(result)

        # Success response
        result = {
            "match": True,
            "song_id": matched_song.id,
            "song_name": matched_song.title,
            "offset": int(offset_diff),
            "offset_seconds": round(offset_diff * 0.32, 2),  # Approximate frame size to seconds
            "hashes_matched_in_input": match_count,
            "input_total_hashes": total_query_hashes,
            "fingerprinted_hashes_in_db": total_song_hashes,
            "input_confidence": round(input_confidence, 2),
            "fingerprinted_confidence": round(db_confidence, 2),
            "total_time": round(t_end - t_start, 2),
            "fingerprint_time": round(t_fingerprint - t_start, 2),
            "query_time": round(t_end - t_fingerprint, 2)
        }
        cache.set(audio_hash, result, timeout=3600)  # Cache for 1 hour
        logger.info(f"Matched song {matched_song.id}: {matched_song.title} with confidence {input_confidence:.2f}%")
        return Response(result)

    except Exception as e:
        logger.exception(f"Error during audio matching: {e}")
        return Response({"error": "Internal server error."}, status=500)

    finally:
        # Clean up temporary files
        try:
            os.remove(original_temp_path)
            if 'wav_path' in locals() and os.path.exists(wav_path):
                os.remove(wav_path)
        except OSError as e:
            logger.error(f"Failed to remove temporary files: {e}")