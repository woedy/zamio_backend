from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from artists.models import Track
from core.utils import get_duration
from music_monitor.models import Dispute, MatchCache, PlayLog
from music_monitor.serializers import DisputeSerializer, MatchCacheSerializer, PlayLogSerializer
from stations.models import Station, StationProgram
from rest_framework.authentication import TokenAuthentication
 



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def flag_match_for_dispute(request):
    payload = {}
    errors = {}

    log_id = request.data.get('playlog_id')
    comment = request.data.get('comment')

    if not log_id:
        errors['playlog_id'] = ['Play log ID is required.']

    if not comment:
        errors['comment'] = ['Comment is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        playlog = PlayLog.objects.get(id=log_id)
    except PlayLog.DoesNotExist:
        errors['playlog_id'] = ['Playlog does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)


    dispute = Dispute.objects.create(
        playlog=playlog,
        dispute_status="Flagged",
        dispute_comments=comment
    )

    playlog.flagged = True
    playlog.save()

    serializer = DisputeSerializer(dispute)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_201_CREATED)







@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_station_disputes_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    station_id = request.query_params.get('station_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station'] = ['Station not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch Dispute
    disputes_qs = Dispute.objects.filter(
        playlog__station=station,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        disputes_qs = disputes_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        disputes_qs = disputes_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        disputes_qs = disputes_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(disputes_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_disputes = []
    for dispute in page.object_list:
        formatted_disputes.append({
            "id": dispute.id,
            "comment": dispute.dispute_comments,
            "status": dispute.dispute_status,
            "track_title": dispute.playlog.track.title,
            "artist_name": dispute.playlog.track.artist.stage_name,
            "duration": get_duration(dispute.playlog.duration),
            "start_time": dispute.playlog.start_time.strftime('%Y-%m-%d ~ %H:%M:%S'),
            "stop_time": dispute.playlog.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S'),
            "confidence": dispute.playlog.avg_confidence_score,
            "earnings": dispute.playlog.royalty_amount,
            "timestamp": timesince(dispute.created_at) + " ago" if dispute.created_at else "Just now"
        })

    data['disputes'] = formatted_disputes
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_disputes_view(request):
    """List disputes for an artist's tracks with pagination and search."""
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Validate artist
    from artists.models import Artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    disputes_qs = Dispute.objects.filter(
        playlog__track__artist=artist,
        is_archived=False
    )

    if search_query:
        disputes_qs = disputes_qs.filter(
            Q(dispute_comments__icontains=search_query) | Q(resolve_comments__icontains=search_query) | Q(playlog__track__title__icontains=search_query)
        )

    if order_by:
        order_map = {
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Status": "dispute_status",
        }
        disputes_qs = disputes_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        disputes_qs = disputes_qs.order_by("-created_at")

    paginator = Paginator(disputes_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    from django.utils.timesince import timesince
    formatted = []
    for d in page.object_list:
        formatted.append({
            "id": d.id,
            "status": d.dispute_status,
            "comment": d.dispute_comments,
            "resolution": d.resolve_comments,
            "track_title": d.playlog.track.title,
            "station_name": d.playlog.station.name,
            "start_time": d.playlog.start_time.strftime('%Y-%m-%d ~ %H:%M:%S') if d.playlog.start_time else None,
            "stop_time": d.playlog.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S') if d.playlog.stop_time else None,
            "duration": get_duration(d.playlog.duration) if d.playlog.duration else None,
            "royalty_amount": float(d.playlog.royalty_amount or 0),
            "ago": timesince(d.created_at) + " ago" if d.created_at else None,
        })

    data['results'] = formatted
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_disputes_admin_view(request):
    """Admin-wide disputes listing with pagination, search and optional filters."""
    payload, data, errors = {}, {}, {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    status_filter = request.query_params.get('status', '').strip()
    station_name = request.query_params.get('station', '').strip()
    artist_name = request.query_params.get('artist', '').strip()
    page_size = int(request.query_params.get('page_size', 10))

    qs = Dispute.objects.select_related('playlog__track__artist', 'playlog__station').filter(is_archived=False)

    if search_query:
        qs = qs.filter(
            Q(dispute_comments__icontains=search_query)
            | Q(resolve_comments__icontains=search_query)
            | Q(playlog__track__title__icontains=search_query)
            | Q(playlog__station__name__icontains=search_query)
            | Q(playlog__track__artist__stage_name__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(dispute_status=status_filter)
    if station_name:
        qs = qs.filter(playlog__station__name__icontains=station_name)
    if artist_name:
        qs = qs.filter(playlog__track__artist__stage_name__icontains=artist_name)

    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    from django.utils.timesince import timesince
    rows = []
    for d in page.object_list:
        pl = d.playlog
        rows.append({
            'id': d.id,
            'status': d.dispute_status,
            'comment': d.dispute_comments,
            'resolution': d.resolve_comments,
            'track_title': getattr(pl.track, 'title', None),
            'artist_name': getattr(pl.track.artist, 'stage_name', None) if getattr(pl, 'track', None) and getattr(pl.track, 'artist', None) else None,
            'station_name': getattr(pl.station, 'name', None),
            'start_time': pl.start_time.strftime('%Y-%m-%d ~ %H:%M:%S') if getattr(pl, 'start_time', None) else None,
            'stop_time': pl.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S') if getattr(pl, 'stop_time', None) else None,
            'duration': get_duration(pl.duration) if getattr(pl, 'duration', None) else None,
            'royalty_amount': float(pl.royalty_amount or 0),
            'confidence': getattr(pl, 'avg_confidence_score', None),
            'timestamp': timesince(d.created_at) + ' ago' if d.created_at else 'Just now',
        })

    data['disputes'] = rows
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
        'count': paginator.count,
        'page_size': page_size,
    }

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_match_dispute_analytics_view(request):
    """Return time-series and summary analytics for a given dispute/playlog.

    - Plays/revenue over time for the track (last 90 days)
    - Station-specific plays/revenue over time (last 90 days)
    - Confidence histogram for the track across all stations (last 90 days)
    - Recent plays for this track on the disputed station
    """
    payload = {}
    errors = {}

    dispute_id = request.query_params.get('dispute_id')
    if not dispute_id:
        errors['dispute_id'] = ['Dispute ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        dispute = Dispute.objects.select_related('playlog__track', 'playlog__station').get(id=dispute_id)
    except Dispute.DoesNotExist:
        errors['dispute_id'] = ['Dispute not found.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    track = dispute.playlog.track
    station = dispute.playlog.station

    from django.utils import timezone
    from datetime import timedelta
    end_date = timezone.now()
    start_date = end_date - timedelta(days=90)

    # Track-wide last 90 days
    track_qs = (
        PlayLog.objects.filter(track=track, played_at__gte=start_date, played_at__lte=end_date)
    )
    track_series = (
        track_qs
        .annotate(day=TruncDate('played_at'))
        .values('day')
        .annotate(plays=Count('id'), revenue=Sum('royalty_amount'), avg_conf=Avg('avg_confidence_score'))
        .order_by('day')
    )
    track_over_time = [
        {
            'date': row['day'].strftime('%Y-%m-%d'),
            'plays': int(row['plays'] or 0),
            'revenue': float(row['revenue'] or 0),
            'avg_confidence': float(row['avg_conf'] or 0),
        }
        for row in track_series
    ]

    # Station-specific last 90 days
    station_qs = track_qs.filter(station=station)
    station_series = (
        station_qs
        .annotate(day=TruncDate('played_at'))
        .values('day')
        .annotate(plays=Count('id'), revenue=Sum('royalty_amount'), avg_conf=Avg('avg_confidence_score'))
        .order_by('day')
    )
    station_over_time = [
        {
            'date': row['day'].strftime('%Y-%m-%d'),
            'plays': int(row['plays'] or 0),
            'revenue': float(row['revenue'] or 0),
            'avg_confidence': float(row['avg_conf'] or 0),
        }
        for row in station_series
    ]

    # Summary totals
    track_totals = track_qs.aggregate(plays=Count('id'), revenue=Sum('royalty_amount'))
    station_totals = station_qs.aggregate(plays=Count('id'), revenue=Sum('royalty_amount'))

    # Confidence histogram buckets
    conf_bins = {'<70': 0, '70-79': 0, '80-89': 0, '90+': 0}
    for val in track_qs.values_list('avg_confidence_score', flat=True):
        if val is None:
            continue
        try:
            v = float(val)
        except Exception:
            continue
        if v < 70:
            conf_bins['<70'] += 1
        elif v < 80:
            conf_bins['70-79'] += 1
        elif v < 90:
            conf_bins['80-89'] += 1
        else:
            conf_bins['90+'] += 1

    # Recent plays on this station for this track
    recent = (
        station_qs.order_by('-played_at')[:10]
        .values('id', 'played_at', 'start_time', 'stop_time', 'royalty_amount', 'avg_confidence_score')
    )
    recent_plays = [
        {
            'id': r['id'],
            'played_at': r['played_at'].strftime('%Y-%m-%d ~ %H:%M:%S') if r['played_at'] else None,
            'start_time': r['start_time'].strftime('%Y-%m-%d ~ %H:%M:%S') if r['start_time'] else None,
            'stop_time': r['stop_time'].strftime('%Y-%m-%d ~ %H:%M:%S') if r['stop_time'] else None,
            'royalty_amount': float(r['royalty_amount'] or 0),
            'avg_confidence_score': float(r['avg_confidence_score'] or 0),
        }
        for r in recent
    ]

    payload['message'] = 'Successful'
    payload['data'] = {
        'track': {
            'title': getattr(track, 'title', None),
            'artist': getattr(getattr(track, 'artist', None), 'stage_name', None),
        },
        'summary': {
            'track_total_plays': int(track_totals['plays'] or 0),
            'track_total_revenue': float(track_totals['revenue'] or 0),
            'station_total_plays': int(station_totals['plays'] or 0),
            'station_total_revenue': float(station_totals['revenue'] or 0),
        },
        'track_over_time': track_over_time,
        'station_over_time': station_over_time,
        'confidence_histogram': conf_bins,
        'recent_station_plays': recent_plays,
    }
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_match_dispute_details_view(request):
    payload = {}
    errors = {}
    data = {}

    dispute_id = request.query_params.get('dispute_id')

    if not dispute_id:
        errors['dispute_id'] = ['Dispute ID is required.']

    try:
        dispute = Dispute.objects.get(id=dispute_id)
    except Dispute.DoesNotExist:
        errors['dispute_id'] = ['Dispute not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)



    track = dispute.playlog.track
    # Prefer the actual play duration from PlayLog; fall back to track duration; else default string
    if getattr(dispute.playlog, 'duration', None):
        duration_str = get_duration(dispute.playlog.duration)
    elif getattr(track, 'duration', None):
        duration_str = get_duration(track.duration)
    else:
        duration_str = "00:00:00"

    data['id'] = dispute.id
    data['track_title'] = getattr(track, 'title', None)
    data['artist_name'] = getattr(getattr(track, 'artist', None), 'stage_name', None)
    data['duration'] = duration_str
    data['cover_art'] = track.cover_art.url if getattr(track.cover_art, 'url', None) else None
    data['audio_file_mp3'] = track.audio_file_mp3.url if getattr(track, 'audio_file_mp3', None) else None
    # Extra useful fields for the UI
    data['dispute_status'] = dispute.dispute_status
    data['dispute_comments'] = dispute.dispute_comments
    data['resolve_comments'] = dispute.resolve_comments
    data['start_time'] = dispute.playlog.start_time.strftime('%Y-%m-%d ~ %H:%M:%S') if getattr(dispute.playlog, 'start_time', None) else None
    data['stop_time'] = dispute.playlog.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S') if getattr(dispute.playlog, 'stop_time', None) else None
    data['avg_confidence_score'] = float(dispute.playlog.avg_confidence_score or 0) if hasattr(dispute.playlog, 'avg_confidence_score') else 0
    data['royalty_amount'] = float(dispute.playlog.royalty_amount or 0) if hasattr(dispute.playlog, 'royalty_amount') else 0




    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)







@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def review_match_for_dispute(request):
    payload = {}
    errors = {}

    dispute_id = request.data.get('dispute_id')
    comment = request.data.get('comment')

    if not dispute_id:
        errors['dispute_id'] = ['Dispute ID is required.']

    if not comment:
        errors['comment'] = ['Comment is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        dispute = Dispute.objects.get(id=dispute_id)
    except Dispute.DoesNotExist:
        errors['dispute_id'] = ['Dispute does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)
    

    # Update dispute status and clear the PlayLog flagged state
    dispute.dispute_status = "Resolved"
    dispute.resolve_comments = comment
    dispute.save()

    try:
        playlog = dispute.playlog
        if playlog and playlog.flagged:
            playlog.flagged = False
            playlog.save(update_fields=["flagged", "updated_at"])
    except Exception:
        # Non-fatal: if we fail to update the playlog flag, still return success for dispute
        pass

    serializer = DisputeSerializer(dispute)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)












from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
@transaction.atomic
def delete_all_matches(request):
    MatchCache.objects.all().delete()
    return HttpResponse("All items deleted successfully.")
