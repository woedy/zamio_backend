
from time import timezone
import uuid
from collections import Counter

from artists.models import Fingerprint, Track
from fan.models import Fan
from music_monitor.models import MatchCache, PlayLog, StreamLog
from music_monitor.utils.match_engine import simple_match
from music_monitor.utils.stream_monitor import StreamMonitor, active_sessions
from stations.models import Station


from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import librosa
from rest_framework.authentication import TokenAuthentication
from django.utils import timezone


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def log_music_play(request):
    payload = {}
    data = {}
    errors = {}

    track_id = request.data.get('track_id')
 
    if not track_id:
        errors['track_id'] = ['Track ID is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    new_stream_log = StreamLog.objects.create(
        track=track,
        played_at=timezone.now(),
    )
    #Optional - Fan ID out for now



    data['track_id'] = track.id

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)




# views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta


ROYALTY_RATE_PER_SECOND = 0.005  # GHS per second
MINIMUM_PLAY_DURATION = 30  # seconds


class LogStreamView(APIView):
    """
    Log a stream by a Fan for a specific Track.
    """

    def post(self, request):
        data = request.data

        track_id = data.get("track_id")
        fan_id = data.get("fan_id")
        start_time = data.get("start_time")
        stop_time = data.get("stop_time")
        stream_source = data.get("stream_source", "web")
        device_id = data.get("device_id", None)

        # Validate required fields
        if not all([track_id, fan_id, start_time, stop_time]):
            return Response({"error": "Missing required fields."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            track = Track.objects.get(pk=track_id, active=True)
            fan = Fan.objects.get(pk=fan_id, active=True, is_archived=False)
        except (Track.DoesNotExist, Fan.DoesNotExist):
            return Response({"error": "Invalid track or fan."}, status=status.HTTP_404_NOT_FOUND)

        # Parse times
        try:
            start_dt = timezone.datetime.fromisoformat(start_time)
            stop_dt = timezone.datetime.fromisoformat(stop_time)
            duration = stop_dt - start_dt
        except ValueError:
            return Response({"error": "Invalid datetime format."}, status=status.HTTP_400_BAD_REQUEST)

        if duration.total_seconds() < MINIMUM_PLAY_DURATION:
            return Response({"error": "Play duration too short."}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent duplicate spam (optional)
        recent = StreamLog.objects.filter(
            track=track,
            fan=fan,
            start_time__gte=timezone.now() - timedelta(minutes=5),
            device_id=device_id
        )
        if recent.exists():
            return Response({"error": "Recent stream already logged."}, status=status.HTTP_409_CONFLICT)

        # Royalty calculation
        royalty_amount = round(duration.total_seconds() * ROYALTY_RATE_PER_SECOND, 2)

        # Create stream log
        stream_log = StreamLog.objects.create(
            track=track,
            fan=fan,
            start_time=start_dt,
            stop_time=stop_dt,
            played_at=start_dt,
            duration=duration,
            royalty_amount=royalty_amount,
            stream_source=stream_source,
            device_id=device_id,
            active=True,
        )

        return Response({
            "message": "✅ Stream logged successfully.",
            "stream_id": stream_log.id,
            "royalty": royalty_amount
        }, status=status.HTTP_201_CREATED)
