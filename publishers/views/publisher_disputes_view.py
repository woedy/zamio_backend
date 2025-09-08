from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.utils.timesince import timesince
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from music_monitor.models import Dispute
from publishers.models import PublisherProfile


User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_publisher_disputes_view(request):
    """List disputes scoped to the current publisher with filters and pagination.

    Query params:
      - publisher_id: optional (fallback to request.user's publisher profile)
      - search: text search on track title, artist stage name, station name
      - status: one of Dispute.STATUS_TYPE values (e.g., Flagged, Pending, Review, Resolved)
      - station: station name substring (optional)
      - date_from (YYYY-MM-DD), date_to (YYYY-MM-DD): filter by playlog.played_at range
      - min_confidence: float, minimum avg confidence score
      - order_by: Newest|Oldest|Confidence|Royalty (optional)
      - page: integer (default 1)
    """
    payload, data, errors = {}, {}, {}

    publisher_id = request.query_params.get('publisher_id', '').strip()
    search_query = request.query_params.get('search', '').strip()
    status_filter = request.query_params.get('status', '').strip()
    station_filter = request.query_params.get('station', '').strip()
    date_from = request.query_params.get('date_from', '').strip()
    date_to = request.query_params.get('date_to', '').strip()
    min_conf_raw = request.query_params.get('min_confidence', '').strip()
    order_by = request.query_params.get('order_by', '').strip()
    page_number = int(request.query_params.get('page', 1))
    page_size = 10

    # Resolve publisher profile
    publisher = None
    if publisher_id:
        try:
            publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
        except PublisherProfile.DoesNotExist:
            errors['publisher_id'] = ['PublisherProfile not found.']
    else:
        try:
            publisher = PublisherProfile.objects.get(user=request.user)
        except PublisherProfile.DoesNotExist:
            errors['publisher'] = ['Publisher profile not found for user.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Base queryset: disputes for plays of this publisher's artists
    disputes_qs = Dispute.objects.select_related(
        'playlog', 'playlog__track', 'playlog__track__artist', 'playlog__station'
    ).filter(
        playlog__track__artist__publisher=publisher,
        is_archived=False,
    )

    # Text search
    if search_query:
        disputes_qs = disputes_qs.filter(
            Q(playlog__track__title__icontains=search_query)
            | Q(playlog__track__artist__stage_name__icontains=search_query)
            | Q(playlog__station__name__icontains=search_query)
        )

    # Status filter
    if status_filter:
        disputes_qs = disputes_qs.filter(dispute_status=status_filter)

    # Station name filter
    if station_filter:
        disputes_qs = disputes_qs.filter(playlog__station__name__icontains=station_filter)

    # Date range filter on played_at
    from django.utils.dateparse import parse_date
    df = parse_date(date_from) if date_from else None
    dt = parse_date(date_to) if date_to else None
    if df and dt:
        from datetime import datetime, timedelta
        from django.utils import timezone
        start = timezone.make_aware(datetime.combine(df, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(dt, datetime.max.time()))
        disputes_qs = disputes_qs.filter(playlog__played_at__range=(start, end))
    elif df:
        from datetime import datetime
        from django.utils import timezone
        start = timezone.make_aware(datetime.combine(df, datetime.min.time()))
        disputes_qs = disputes_qs.filter(playlog__played_at__gte=start)
    elif dt:
        from datetime import datetime
        from django.utils import timezone
        end = timezone.make_aware(datetime.combine(dt, datetime.max.time()))
        disputes_qs = disputes_qs.filter(playlog__played_at__lte=end)

    # Min confidence filter
    if min_conf_raw:
        try:
            min_conf = float(min_conf_raw)
            disputes_qs = disputes_qs.filter(playlog__avg_confidence_score__gte=min_conf)
        except ValueError:
            pass

    # Ordering mapping
    if order_by:
        order_map = {
            'Newest': '-created_at',
            'Oldest': 'created_at',
            'Confidence': '-playlog__avg_confidence_score',
            'Royalty': '-playlog__royalty_amount',
        }
        disputes_qs = disputes_qs.order_by(order_map.get(order_by, '-created_at'))
    else:
        disputes_qs = disputes_qs.order_by('-created_at')

    # Paginate
    paginator = Paginator(disputes_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Serialize rows
    rows = []
    for d in page.object_list:
        pl = d.playlog
        track = pl.track
        artist = getattr(track, 'artist', None)
        station = pl.station
        rows.append({
            'id': d.id,
            'track_title': getattr(track, 'title', None),
            'artist_name': getattr(artist, 'stage_name', None),
            'station_name': getattr(station, 'name', None),
            'station_region': getattr(station, 'region', None),
            'played_at': pl.played_at.isoformat() if getattr(pl, 'played_at', None) else None,
            'confidence': float(pl.avg_confidence_score or 0) if hasattr(pl, 'avg_confidence_score') else 0,
            'royalty': float(pl.royalty_amount or 0) if hasattr(pl, 'royalty_amount') else 0,
            'dispute_status': d.dispute_status,
            'comment': d.dispute_comments,
            'age': timesince(d.created_at) + ' ago' if getattr(d, 'created_at', None) else None,
            'flagged': bool(pl.flagged),
        })

    data['disputes'] = rows
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'count': paginator.count,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

