from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q, Sum, Count, Avg
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist, Track
from publishers.models import PublisherProfile
from music_monitor.models import PlayLog, StreamLog

User = get_user_model()


def _get_publisher_for_request(request):
    publisher_id = request.query_params.get('publisher_id')
    publisher = None
    errors = {}
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
    return publisher, errors


def _parse_date_range(request):
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    start = parse_date(date_from) if date_from else None
    end = parse_date(date_to) if date_to else None
    # Normalize end to end-of-day if provided
    if end:
        end = timezone.make_aware(timezone.datetime.combine(end, timezone.datetime.max.time()))
    if start:
        start = timezone.make_aware(timezone.datetime.combine(start, timezone.datetime.min.time()))
    return start, end


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_managed_artists_royalties_view(request):
    payload, data, errors = {}, {}, {}

    publisher, errs = _get_publisher_for_request(request)
    if errs:
        errors.update(errs)

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = int(request.query_params.get('page_size', 10))
    order_by = request.query_params.get('order_by', 'Royalties')  # Name|Plays|Royalties

    start, end = _parse_date_range(request)

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    artists_qs = Artist.objects.filter(is_archived=False, publisher=publisher)
    if search_query:
        artists_qs = artists_qs.filter(Q(stage_name__icontains=search_query) | Q(user__first_name__icontains=search_query) | Q(user__last_name__icontains=search_query))

    rows = []
    for a in artists_qs.select_related('user'):
        tracks = Track.objects.filter(artist=a, is_archived=False)
        pl_qs = PlayLog.objects.filter(track__in=tracks)
        sl_qs = StreamLog.objects.filter(track__in=tracks)
        if start and end:
            pl_qs = pl_qs.filter(played_at__range=(start, end))
            sl_qs = sl_qs.filter(played_at__range=(start, end))
        elif start:
            pl_qs = pl_qs.filter(played_at__gte=start)
            sl_qs = sl_qs.filter(played_at__gte=start)
        elif end:
            pl_qs = pl_qs.filter(played_at__lte=end)
            sl_qs = sl_qs.filter(played_at__lte=end)

        radio_plays = pl_qs.count()
        stream_plays = sl_qs.count()
        radio_royalties = pl_qs.aggregate(total=Sum('royalty_amount'))['total'] or 0
        stream_royalties = sl_qs.aggregate(total=Sum('royalty_amount'))['total'] or 0
        last_play = pl_qs.order_by('-played_at').values_list('played_at', flat=True).first() or sl_qs.order_by('-played_at').values_list('played_at', flat=True).first()

        rows.append({
            'artist_id': a.artist_id,
            'stage_name': a.stage_name,
            'photo': a.user.photo.url if getattr(a.user, 'photo', None) else None,
            'radioPlays': radio_plays,
            'streamPlays': stream_plays,
            'totalPlays': radio_plays + stream_plays,
            'radioRoyalties': float(radio_royalties),
            'streamingRoyalties': float(stream_royalties),
            'totalRoyalties': float((radio_royalties or 0) + (stream_royalties or 0)),
            'lastPlayedAt': last_play.isoformat() if last_play else None,
        })

    if order_by == 'Name':
        rows.sort(key=lambda r: (r['stage_name'] or '').lower())
    elif order_by == 'Plays':
        rows.sort(key=lambda r: r['totalPlays'], reverse=True)
    else:  # Royalties
        rows.sort(key=lambda r: r['totalRoyalties'], reverse=True)

    paginator = Paginator(rows, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    data['artists'] = list(page.object_list)
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_royalties_detail_view(request):
    payload, data, errors = {}, {}, {}

    publisher, errs = _get_publisher_for_request(request)
    if errs:
        errors.update(errs)

    artist_id = request.query_params.get('artist_id')
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required']
    else:
        try:
            artist = Artist.objects.get(artist_id=artist_id, publisher=publisher)
        except Artist.DoesNotExist:
            errors['artist_id'] = ['Artist not found for this publisher']

    start, end = _parse_date_range(request)

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    tracks = Track.objects.filter(artist=artist, is_archived=False)
    pl_qs = PlayLog.objects.filter(track__in=tracks)
    sl_qs = StreamLog.objects.filter(track__in=tracks)
    if start and end:
        pl_qs = pl_qs.filter(played_at__range=(start, end))
        sl_qs = sl_qs.filter(played_at__range=(start, end))
    elif start:
        pl_qs = pl_qs.filter(played_at__gte=start)
        sl_qs = sl_qs.filter(played_at__gte=start)
    elif end:
        pl_qs = pl_qs.filter(played_at__lte=end)
        sl_qs = sl_qs.filter(played_at__lte=end)

    # Summary
    radio_plays = pl_qs.count()
    streaming_plays = sl_qs.count()
    radio_royalties = float(pl_qs.aggregate(total=Sum('royalty_amount'))['total'] or 0)
    streaming_royalties = float(sl_qs.aggregate(total=Sum('royalty_amount'))['total'] or 0)
    avg_conf = float(pl_qs.aggregate(avg=Avg('avg_confidence_score'))['avg'] or 0)
    paid = float(pl_qs.filter(claimed=True).aggregate(total=Sum('royalty_amount'))['total'] or 0) + float(sl_qs.filter(claimed=True).aggregate(total=Sum('royalty_amount'))['total'] or 0)
    pending = (radio_royalties + streaming_royalties) - paid

    data['summary'] = {
        'artist_id': artist.artist_id,
        'stage_name': artist.stage_name,
        'photo': artist.user.photo.url if getattr(artist.user, 'photo', None) else None,
        'radioPlays': radio_plays,
        'streamPlays': streaming_plays,
        'totalPlays': radio_plays + streaming_plays,
        'radioRoyalties': radio_royalties,
        'streamingRoyalties': streaming_royalties,
        'totalRoyalties': radio_royalties + streaming_royalties,
        'paidRoyalties': paid,
        'pendingRoyalties': max(pending, 0.0),
        'avgConfidence': avg_conf,
    }

    # Per-track breakdown
    track_rows = []
    for t in tracks.select_related('genre', 'album'):
        t_pl = pl_qs.filter(track=t)
        t_sl = sl_qs.filter(track=t)
        row = {
            'track_id': t.track_id,
            'title': t.title,
            'album': t.album.title if t.album else None,
            'genre': t.genre.name if t.genre else None,
            'radioPlays': t_pl.count(),
            'streamPlays': t_sl.count(),
            'radioRoyalties': float(t_pl.aggregate(total=Sum('royalty_amount'))['total'] or 0),
            'streamingRoyalties': float(t_sl.aggregate(total=Sum('royalty_amount'))['total'] or 0),
        }
        row['totalPlays'] = row['radioPlays'] + row['streamPlays']
        row['totalRoyalties'] = row['radioRoyalties'] + row['streamingRoyalties']
        track_rows.append(row)
    track_rows.sort(key=lambda r: r['totalRoyalties'], reverse=True)
    data['tracks'] = track_rows

    # Top stations by royalties
    station_rows = pl_qs.values('station__name').annotate(plays=Count('id'), royalties=Sum('royalty_amount')).order_by('-royalties')[:10]
    data['topStations'] = [
        {
            'station': r['station__name'],
            'plays': r['plays'],
            'royalties': float(r['royalties'] or 0),
        }
        for r in station_rows
    ]

    # Monthly trend (last 6 months)
    from django.db.models.functions import TruncMonth
    trend = (
        pl_qs.annotate(month=TruncMonth('played_at')).values('month').annotate(royalties=Sum('royalty_amount')).order_by('month')
    )
    trend_stream = (
        sl_qs.annotate(month=TruncMonth('played_at')).values('month').annotate(royalties=Sum('royalty_amount')).order_by('month')
    )
    # Merge months
    by_month = {}
    for r in trend:
        by_month[r['month']] = {'radio': float(r['royalties'] or 0), 'stream': 0.0}
    for r in trend_stream:
        if r['month'] in by_month:
            by_month[r['month']]['stream'] = float(r['royalties'] or 0)
        else:
            by_month[r['month']] = {'radio': 0.0, 'stream': float(r['royalties'] or 0)}
    months_sorted = sorted([m for m in by_month.keys() if m], key=lambda d: d)
    data['monthlyTrend'] = [
        {
            'month': m.date().isoformat(),
            'radioRoyalties': by_month[m]['radio'],
            'streamingRoyalties': by_month[m]['stream'],
            'totalRoyalties': by_month[m]['radio'] + by_month[m]['stream'],
        }
        for m in months_sorted[-6:]
    ]

    # Recent logs
    recent_radio = pl_qs.order_by('-played_at')[:10]
    recent_stream = sl_qs.order_by('-played_at')[:10]
    recent = []
    for log in recent_radio:
        recent.append({
            'id': log.id,
            'date': log.played_at.isoformat() if log.played_at else None,
            'source': 'Radio',
            'station': log.station.name if log.station else None,
            'song': log.track.title,
            'royalty': float(log.royalty_amount or 0),
            'confidence': float(log.avg_confidence_score or 0),
        })
    for log in recent_stream:
        recent.append({
            'id': log.id,
            'date': log.played_at.isoformat() if log.played_at else None,
            'source': 'Streaming',
            'station': None,
            'song': log.track.title,
            'royalty': float(log.royalty_amount or 0),
            'confidence': float(log.avg_confidence_score or 0),
        })
    recent.sort(key=lambda r: r['date'] or '', reverse=True)
    data['recentLogs'] = recent[:10]

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

