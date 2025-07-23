
from time import timezone
import uuid
from collections import Counter

from artists.models import Fingerprint, Track
from music_monitor.models import MatchCache, PlayLog
from music_monitor.utils.match_engine import simple_match, simple_match_mp3
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
def start_stream_monitoring(request):
    """Start monitoring a radio stream"""
    try:
        stream_url = request.data.get('stream_url')
        station_id = request.data.get('station_id')
        
        if not stream_url or not station_id:
            return Response({
                'error': 'stream_url and station_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate station exists
        try:
            station = Station.objects.get(station_id=station_id)
        except Station.DoesNotExist:
            return Response({
                'error': 'Station not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Create and start monitor
        monitor = StreamMonitor(session_id, stream_url, station_id)
        monitor.start()
        
        # Store in active sessions
        active_sessions[session_id] = monitor
        
        return Response({
            'session_id': session_id,
            'message': 'Stream monitoring started successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to start monitoring: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def stop_stream_monitoring(request, session_id):
    """Stop monitoring a radio stream"""
    try:
        if session_id not in active_sessions:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        # Stop the monitor
        monitor = active_sessions[session_id]
        monitor.stop()
        
        # Remove from active sessions
        del active_sessions[session_id]
        
        return Response({
            'message': 'Stream monitoring stopped successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to stop monitoring: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_stream_matches(request, session_id):
    """Get recent matches for a monitoring session"""
    try:
        if session_id not in active_sessions:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        monitor = active_sessions[session_id]
        
        return Response({
            'matches': monitor.matches,
            'session_active': monitor.is_running
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to get matches: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_active_sessions(request):
    """Get list of active monitoring sessions"""
    try:
        sessions = []
        for session_id, monitor in active_sessions.items():
            sessions.append({
                'session_id': session_id,
                'station_id': monitor.station_id,
                'stream_url': monitor.stream_url,
                'is_running': monitor.is_running,
                'matches_count': len(monitor.matches)
            })
            
        return Response({
            'active_sessions': sessions
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to get sessions: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






# views/upload_audio.py




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def upload_audio_match2222(request):
    """
    Accepts an uploaded audio file and station ID, matches it,
    and logs the result into MatchCache (and PlayLog if needed).
    """
    audio_file = request.FILES.get('file')
    station_id = request.POST.get('station_id')

    if not audio_file:
        return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)
    if not station_id:
        return Response({'error': 'Station ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        return Response({'error': 'Invalid station ID'}, status=status.HTTP_404_NOT_FOUND)

    try:
        samples, sr = librosa.load(audio_file, sr=44100)

        if len(samples) == 0:
            return Response({'error': 'Empty audio data'}, status=status.HTTP_400_BAD_REQUEST)


        # Get fingerprints
        fingerprints = [
            (fp.track.id, fp.hash, fp.offset)
            for fp in Fingerprint.objects.select_related('track').all()
        ]

        match_result = simple_match(samples, sr, fingerprints)

        if match_result["match"]:
            track = Track.objects.get(id=match_result["song_id"])

            # Save to MatchCache
            match_cache = MatchCache.objects.create(
                track=track,
                station=station,
                station_program=None,
                matched_at=timezone.now()
            )

            return Response({
                'match': True,
                'track_title': track.title,
                'artist_name': track.artist.stage_name,
                'album_title': track.album.title if track.album else None,
                'confidence': min(100, (match_result["hashes_matched"] / 20) * 100),
                'hashes_matched': match_result["hashes_matched"]
            }, status=status.HTTP_200_OK)
        
    
        return Response({'match': False}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': f'Processing error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication

from django.utils import timezone
from django.core.management import call_command

import librosa
import tempfile
import os

from music_monitor.models import MatchCache
from stations.models import Station
from artists.models import Track, Fingerprint

from collections import Counter
from datetime import timedelta


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def upload_audio_match(request):
    """
    Uploads an audio clip, matches it to known fingerprints, and logs to MatchCache.
    """
    audio_file = request.FILES.get('file')
    station_id = request.POST.get('station_id')

    if not audio_file:
        return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)
    if not station_id:
        return Response({'error': 'Station ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        return Response({'error': 'Invalid station ID'}, status=status.HTTP_404_NOT_FOUND)

    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            for chunk in audio_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        samples, sr = librosa.load(temp_path, sr=44100)
        os.remove(temp_path)

        if len(samples) == 0:
            return Response({'error': 'Empty audio data'}, status=status.HTTP_400_BAD_REQUEST)

        # Collect all known fingerprints
        fingerprints = Fingerprint.objects.select_related('track').values_list('track_id', 'hash', 'offset')
        fingerprints = list(fingerprints)

        result = simple_match_mp3(samples, sr, fingerprints)

        if result['match']:
            track = Track.objects.get(id=result['song_id'])
            hashes_matched = result['hashes_matched']
            confidence_score = min(100, (hashes_matched / 20) * 100)  # Assuming 20 is baseline

            MatchCache.objects.create(
                track=track,
                station=station,
                station_program=None,
                matched_at=timezone.now(),
                avg_confidence_score=confidence_score,
                processed=False
            )

            # Optional: Trigger match processing right away
            # from django.core.management import call_command
            # call_command('process_matches')

            return Response({
                'match': True,
                'track_title': track.title,
                'artist_name': track.artist.stage_name,
                'album_title': track.album.title if track.album else None,
                'confidence': round(confidence_score, 2),
                'hashes_matched': hashes_matched
            }, status=status.HTTP_200_OK)

        else:
            return Response({'match': False, 'reason': result['reason']}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': f'Processing error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




