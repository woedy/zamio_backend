import csv
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q, Count, Avg
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Track
from music_monitor.models import PlayLog, AudioDetection, MatchCache
from stations.models import Station
from stations.serializers import StationPlayLogSerializer, StationMatchCacheSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
@parser_classes([MultiPartParser, FormParser])
def upload_playlog(request):
    """Upload and process station playlog in CSV, XML, or JSON format"""
    payload = {}
    errors = {}

    station_id = request.data.get('station_id', '')
    file_format = request.data.get('format', 'csv').lower()
    uploaded_file = request.FILES.get('playlog_file')

    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not uploaded_file:
        errors['playlog_file'] = ['Playlog file is required.']
    if file_format not in ['csv', 'xml', 'json']:
        errors['format'] = ['Format must be csv, xml, or json.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Read and parse the uploaded file
        file_content = uploaded_file.read().decode('utf-8')
        
        if file_format == 'csv':
            playlog_entries = parse_csv_playlog(file_content)
        elif file_format == 'xml':
            playlog_entries = parse_xml_playlog(file_content)
        elif file_format == 'json':
            playlog_entries = parse_json_playlog(file_content)
        
        # Process and validate entries
        processed_count = 0
        skipped_count = 0
        error_entries = []
        
        for entry in playlog_entries:
            try:
                # Validate required fields
                if not all([entry.get('title'), entry.get('artist'), entry.get('played_at')]):
                    skipped_count += 1
                    error_entries.append({
                        'entry': entry,
                        'error': 'Missing required fields (title, artist, played_at)'
                    })
                    continue
                
                # Try to find matching track
                track = find_matching_track(entry['title'], entry['artist'])
                
                if track:
                    # Create PlayLog entry
                    play_log = PlayLog.objects.create(
                        track=track,
                        station=station,
                        source='Radio',
                        played_at=parse_datetime(entry['played_at']),
                        start_time=parse_datetime(entry.get('start_time')) if entry.get('start_time') else None,
                        stop_time=parse_datetime(entry.get('stop_time')) if entry.get('stop_time') else None,
                        duration=parse_duration(entry.get('duration')) if entry.get('duration') else None,
                        avg_confidence_score=Decimal('1.0'),  # Manual upload gets high confidence
                        active=True
                    )
                    processed_count += 1
                else:
                    # Track not found, create entry for manual verification
                    skipped_count += 1
                    error_entries.append({
                        'entry': entry,
                        'error': f'Track not found: {entry["title"]} by {entry["artist"]}'
                    })
                    
            except Exception as e:
                skipped_count += 1
                error_entries.append({
                    'entry': entry,
                    'error': str(e)
                })
        
        payload['message'] = 'Playlog upload completed'
        payload['data'] = {
            'processed_count': processed_count,
            'skipped_count': skipped_count,
            'total_entries': len(playlog_entries),
            'error_entries': error_entries[:10]  # Limit to first 10 errors
        }
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        payload['message'] = 'Failed to process playlog file'
        payload['errors'] = {'file': [str(e)]}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_playlog_comparison(request):
    """Compare uploaded playlogs with detected matches"""
    payload = {}
    errors = {}

    station_id = request.query_params.get('station_id', '')
    date_from = request.query_params.get('date_from', '')
    date_to = request.query_params.get('date_to', '')
    page_number = request.query_params.get('page', 1)
    page_size = int(request.query_params.get('page_size', 20))

    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Build date filter
    date_filter = {}
    if date_from:
        try:
            date_filter['played_at__gte'] = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            errors['date_from'] = ['Invalid date format. Use YYYY-MM-DD.']
    
    if date_to:
        try:
            date_filter['played_at__lte'] = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            errors['date_to'] = ['Invalid date format. Use YYYY-MM-DD.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Get playlogs and detections for comparison
    playlogs = PlayLog.objects.filter(
        station=station,
        is_archived=False,
        **date_filter
    ).order_by('-played_at')

    detections = AudioDetection.objects.filter(
        station=station,
        processing_status='completed',
        **{f'detected_at__{k}': v for k, v in date_filter.items()}
    ).order_by('-detected_at')

    # Paginate playlogs
    paginator = Paginator(playlogs, page_size)
    try:
        paginated_playlogs = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_playlogs = paginator.page(1)
    except EmptyPage:
        paginated_playlogs = paginator.page(paginator.num_pages)

    # Create comparison data
    comparison_data = []
    for playlog in paginated_playlogs:
        # Find matching detections within a time window (±5 minutes)
        time_window_start = playlog.played_at - timedelta(minutes=5)
        time_window_end = playlog.played_at + timedelta(minutes=5)
        
        matching_detections = detections.filter(
            detected_at__gte=time_window_start,
            detected_at__lte=time_window_end,
            track=playlog.track
        )
        
        comparison_entry = {
            'playlog': StationPlayLogSerializer(playlog).data,
            'matching_detections': len(matching_detections),
            'detection_confidence': matching_detections.aggregate(
                avg_confidence=Avg('confidence_score')
            )['avg_confidence'] or 0,
            'discrepancy': len(matching_detections) == 0,
            'multiple_matches': len(matching_detections) > 1
        }
        comparison_data.append(comparison_entry)

    # Calculate summary statistics
    total_playlogs = playlogs.count()
    total_detections = detections.count()
    matched_entries = sum(1 for entry in comparison_data if not entry['discrepancy'])
    discrepancy_rate = ((total_playlogs - matched_entries) / total_playlogs * 100) if total_playlogs > 0 else 0

    payload['message'] = 'Playlog comparison completed'
    payload['data'] = {
        'comparison_data': comparison_data,
        'pagination': {
            'page_number': paginated_playlogs.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'next': paginated_playlogs.next_page_number() if paginated_playlogs.has_next() else None,
            'previous': paginated_playlogs.previous_page_number() if paginated_playlogs.has_previous() else None,
        },
        'summary': {
            'total_playlogs': total_playlogs,
            'total_detections': total_detections,
            'matched_entries': matched_entries,
            'discrepancy_rate': round(discrepancy_rate, 2)
        }
    }

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_match_log_details(request):
    """Get detailed match log with confidence scores and detection metadata"""
    payload = {}
    errors = {}

    station_id = request.query_params.get('station_id', '')
    detection_source = request.query_params.get('source', '')  # 'local', 'acrcloud', 'all'
    confidence_threshold = request.query_params.get('confidence_threshold', '0.0')
    page_number = request.query_params.get('page', 1)
    page_size = int(request.query_params.get('page_size', 20))

    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']

    try:
        confidence_threshold = float(confidence_threshold)
    except ValueError:
        errors['confidence_threshold'] = ['Invalid confidence threshold.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Build query filters
    detections_qs = AudioDetection.objects.filter(
        station=station,
        confidence_score__gte=confidence_threshold
    )

    if detection_source and detection_source != 'all':
        detections_qs = detections_qs.filter(detection_source=detection_source)

    detections_qs = detections_qs.order_by('-detected_at')

    # Paginate results
    paginator = Paginator(detections_qs, page_size)
    try:
        paginated_detections = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_detections = paginator.page(1)
    except EmptyPage:
        paginated_detections = paginator.page(paginator.num_pages)

    # Serialize detection data with additional metadata
    detection_data = []
    for detection in paginated_detections:
        detection_info = {
            'id': detection.id,
            'detection_id': str(detection.detection_id),
            'track_title': detection.detected_title or (detection.track.title if detection.track else 'Unknown'),
            'artist_name': detection.detected_artist or (detection.track.artist.stage_name if detection.track and detection.track.artist else 'Unknown'),
            'album': detection.detected_album,
            'detection_source': detection.detection_source,
            'confidence_score': float(detection.confidence_score),
            'processing_status': detection.processing_status,
            'detected_at': detection.detected_at.isoformat(),
            'audio_timestamp': detection.audio_timestamp.isoformat(),
            'duration_seconds': detection.duration_seconds,
            'isrc': detection.isrc,
            'pro_affiliation': detection.get_pro_display_name(),
            'fingerprint_version': detection.fingerprint_version,
            'retry_count': detection.retry_count,
            'processing_time_ms': detection.processing_time_ms,
            'has_track_match': detection.track is not None,
            'error_message': detection.error_message
        }
        detection_data.append(detection_info)

    # Calculate statistics
    stats = detections_qs.aggregate(
        total_detections=Count('id'),
        avg_confidence=Avg('confidence_score'),
        local_count=Count('id', filter=Q(detection_source='local')),
        acrcloud_count=Count('id', filter=Q(detection_source='acrcloud')),
        high_confidence_count=Count('id', filter=Q(confidence_score__gte=0.8)),
        matched_tracks_count=Count('id', filter=Q(track__isnull=False))
    )

    payload['message'] = 'Match log details retrieved successfully'
    payload['data'] = {
        'detections': detection_data,
        'pagination': {
            'page_number': paginated_detections.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'next': paginated_detections.next_page_number() if paginated_detections.has_next() else None,
            'previous': paginated_detections.previous_page_number() if paginated_detections.has_previous() else None,
        },
        'statistics': {
            'total_detections': stats['total_detections'] or 0,
            'average_confidence': round(float(stats['avg_confidence'] or 0), 4),
            'local_detections': stats['local_count'] or 0,
            'acrcloud_detections': stats['acrcloud_count'] or 0,
            'high_confidence_detections': stats['high_confidence_count'] or 0,
            'matched_tracks': stats['matched_tracks_count'] or 0,
            'match_rate': round((stats['matched_tracks_count'] or 0) / (stats['total_detections'] or 1) * 100, 2)
        }
    }

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def verify_detection_match(request):
    """Manually verify or correct a low-confidence detection match"""
    payload = {}
    errors = {}

    detection_id = request.data.get('detection_id', '')
    action = request.data.get('action', '')  # 'confirm', 'correct', 'reject'
    track_id = request.data.get('track_id', '')
    notes = request.data.get('notes', '')

    if not detection_id:
        errors['detection_id'] = ['Detection ID is required.']
    if action not in ['confirm', 'correct', 'reject']:
        errors['action'] = ['Action must be confirm, correct, or reject.']

    try:
        detection = AudioDetection.objects.get(detection_id=detection_id)
    except AudioDetection.DoesNotExist:
        errors['detection_id'] = ['Detection does not exist.']

    if action in ['confirm', 'correct'] and not track_id:
        errors['track_id'] = ['Track ID is required for confirm/correct actions.']

    if action in ['confirm', 'correct'] and track_id:
        try:
            track = Track.objects.get(id=track_id)
        except Track.DoesNotExist:
            errors['track_id'] = ['Track does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        if action == 'confirm':
            # Confirm the existing match
            detection.processing_status = 'completed'
            detection.confidence_score = max(detection.confidence_score, Decimal('0.9'))  # Boost confidence for manual confirmation
            
        elif action == 'correct':
            # Correct the match with a different track
            detection.track = track
            detection.processing_status = 'completed'
            detection.confidence_score = Decimal('0.95')  # High confidence for manual correction
            detection.detected_title = track.title
            detection.detected_artist = track.artist.stage_name if track.artist else ''
            
        elif action == 'reject':
            # Reject the match
            detection.track = None
            detection.processing_status = 'failed'
            detection.error_message = f"Manually rejected: {notes}" if notes else "Manually rejected by station staff"

        # Add verification notes
        if notes:
            existing_metadata = detection.external_metadata or {}
            existing_metadata['manual_verification'] = {
                'action': action,
                'notes': notes,
                'verified_by': request.user.email,
                'verified_at': timezone.now().isoformat()
            }
            detection.external_metadata = existing_metadata

        detection.save()

        # If confirmed or corrected, create/update PlayLog entry
        if action in ['confirm', 'correct'] and detection.track:
            playlog, created = PlayLog.objects.get_or_create(
                track=detection.track,
                station=detection.station,
                played_at=detection.audio_timestamp,
                defaults={
                    'source': 'Radio',
                    'start_time': detection.audio_timestamp,
                    'duration': timedelta(seconds=detection.duration_seconds) if detection.duration_seconds else None,
                    'avg_confidence_score': detection.confidence_score,
                    'active': True
                }
            )

        payload['message'] = f'Detection {action}ed successfully'
        payload['data'] = {
            'detection_id': str(detection.detection_id),
            'new_status': detection.processing_status,
            'confidence_score': float(detection.confidence_score),
            'track_matched': detection.track.title if detection.track else None
        }

        return Response(payload, status=status.HTTP_200_OK)

    except Exception as e:
        payload['message'] = 'Failed to verify detection'
        payload['errors'] = {'verification': [str(e)]}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)


# Helper functions

def parse_csv_playlog(content):
    """Parse CSV playlog content"""
    entries = []
    reader = csv.DictReader(StringIO(content))
    
    for row in reader:
        entry = {
            'title': row.get('title', '').strip(),
            'artist': row.get('artist', '').strip(),
            'album': row.get('album', '').strip(),
            'played_at': row.get('played_at', '').strip(),
            'start_time': row.get('start_time', '').strip(),
            'stop_time': row.get('stop_time', '').strip(),
            'duration': row.get('duration', '').strip()
        }
        entries.append(entry)
    
    return entries


def parse_xml_playlog(content):
    """Parse XML playlog content"""
    entries = []
    root = ET.fromstring(content)
    
    for item in root.findall('.//item') or root.findall('.//entry') or root.findall('.//track'):
        entry = {
            'title': (item.find('title') or item.find('name')).text if (item.find('title') or item.find('name')) is not None else '',
            'artist': item.find('artist').text if item.find('artist') is not None else '',
            'album': item.find('album').text if item.find('album') is not None else '',
            'played_at': item.find('played_at').text if item.find('played_at') is not None else '',
            'start_time': item.find('start_time').text if item.find('start_time') is not None else '',
            'stop_time': item.find('stop_time').text if item.find('stop_time') is not None else '',
            'duration': item.find('duration').text if item.find('duration') is not None else ''
        }
        entries.append(entry)
    
    return entries


def parse_json_playlog(content):
    """Parse JSON playlog content"""
    data = json.loads(content)
    
    # Handle different JSON structures
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get('entries', []) or data.get('tracks', []) or data.get('playlist', [])
    else:
        raise ValueError("Invalid JSON structure")
    
    # Normalize field names
    normalized_entries = []
    for entry in entries:
        normalized_entry = {
            'title': entry.get('title') or entry.get('name') or entry.get('track_name', ''),
            'artist': entry.get('artist') or entry.get('artist_name', ''),
            'album': entry.get('album') or entry.get('album_name', ''),
            'played_at': entry.get('played_at') or entry.get('timestamp') or entry.get('time', ''),
            'start_time': entry.get('start_time', ''),
            'stop_time': entry.get('stop_time') or entry.get('end_time', ''),
            'duration': entry.get('duration', '')
        }
        normalized_entries.append(normalized_entry)
    
    return normalized_entries


def find_matching_track(title, artist):
    """Find matching track in the database"""
    # Try exact match first
    tracks = Track.objects.filter(
        title__iexact=title,
        artist__stage_name__iexact=artist,
        is_archived=False
    )
    
    if tracks.exists():
        return tracks.first()
    
    # Try fuzzy matching
    tracks = Track.objects.filter(
        title__icontains=title.split()[0] if title.split() else title,
        artist__stage_name__icontains=artist.split()[0] if artist.split() else artist,
        is_archived=False
    )
    
    if tracks.exists():
        return tracks.first()
    
    return None


def parse_datetime(datetime_str):
    """Parse datetime string in various formats"""
    if not datetime_str:
        return None
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {datetime_str}")


def parse_duration(duration_str):
    """Parse duration string in various formats"""
    if not duration_str:
        return None
    
    try:
        # Try parsing as seconds
        seconds = float(duration_str)
        return timedelta(seconds=seconds)
    except ValueError:
        pass
    
    try:
        # Try parsing as MM:SS or HH:MM:SS
        parts = duration_str.split(':')
        if len(parts) == 2:
            minutes, seconds = map(int, parts)
            return timedelta(minutes=minutes, seconds=seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
    except ValueError:
        pass
    
    return None