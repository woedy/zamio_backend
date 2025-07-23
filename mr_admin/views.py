from datetime import datetime, timedelta
import random
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from django.db.models.functions import ExtractMonth, ExtractWeekDay, TruncDate
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status

from artists.models import Artist, PlatformAvailability, Track
from music_monitor.models import PlayLog
from stations.models import Station

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_admin_dashboard_data(request):
    now = timezone.now()
    # Period filtering
    period = request.query_params.get('period', 'monthly')
    sd_str = request.query_params.get('start_date')
    ed_str = request.query_params.get('end_date')

    start_date = end_date = None
    if sd_str and ed_str:
        try:
            sd = datetime.strptime(sd_str, '%Y-%m-%d')
            ed = datetime.strptime(ed_str, '%Y-%m-%d') + timedelta(days=1)
            start_date = timezone.make_aware(sd)
            end_date = timezone.make_aware(ed)
        except ValueError:
            return Response({"message": "Invalid date format; use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        if period == 'daily':
            start_date = now - timedelta(days=1)
        elif period == 'weekly':
            start_date = now - timedelta(weeks=1)
        elif period == 'monthly':
            start_date = now - timedelta(days=30)
        else:
            # all-time
            pass

    logs = PlayLog.objects.filter(active=True)
    if start_date:
        logs = logs.filter(played_at__gte=start_date)
    if end_date:
        logs = logs.filter(played_at__lt=end_date)

    # Base stats
    total_stations = Station.objects.count()
    total_artists = Artist.objects.count()
    total_songs = Track.objects.count()
    total_plays = logs.count()
    total_royalties = float(logs.aggregate(sum=Sum('royalty_amount'))['sum'] or 0)
    pending_payments = float(logs.filter(flagged=True).aggregate(sum=Sum('royalty_amount'))['sum'] or 0)

    # Station performance: top 5
    st_qs = logs.values('station__name').annotate(
        plays=Count('id'),
        revenue=Sum('royalty_amount')
    ).order_by('-revenue')[:5]
    station_performance = [
        {"station": r['station__name'], "plays": r['plays'], "revenue": float(r['revenue'] or 0)}
        for r in st_qs
    ]

    # Top earners (artists)
    artist_qs = Artist.objects.annotate(
        plays=Count('track__track_playlog', filter=Q(track__track_playlog__active=True)),
        earnings=Sum('track__track_playlog__royalty_amount', filter=Q(track__track_playlog__active=True))
    ).order_by('-earnings')[:5]
    top_earners = [
        {"name": a.stage_name, "plays": a.plays, "totalEarnings": float(a.earnings or 0)}
        for a in artist_qs
    ]

    # Distribution: by platform
    dist_qs = PlatformAvailability.objects.filter(track__track_playlog__active=True)
    platform_stats = dist_qs.values('platform').annotate(
        tracks=Count('track', distinct=True),
        revenue=Sum('track__track_playlog__royalty_amount')
    )
    distribution_metrics = [
        {
            "platform": r['platform'],
            "tracks": r['tracks'],
            "revenue": float(r['revenue'] or 0)
        } for r in platform_stats
    ]

    # Revenue and artist+station creation over time
    time_qs = []
    if start_date:
        tb = TruncDate('played_at')
        time_qs = logs.annotate(day=tb).values('day').annotate(
            revenue=Sum('royalty_amount'),
            plays=Count('id')
        ).order_by('day')
    revenue_data = [
        {"day": r['day'].strftime('%Y-%m-%d'), "revenue": float(r['revenue']), "plays": r['plays']}
        for r in time_qs
    ]

    # Genre breakdown
    genre_qs = Track.objects.filter(track_playlog__active=True).values('genre__name').annotate(
        plays=Count('track_playlog')
    )
    genre_data = [
        {"name": r['genre__name'] or "Unknown", "value": r['plays']} for r in genre_qs
    ]

    # Daily activity counts (last week)
    da_qs = logs.filter(played_at__gte=now - timedelta(days=7)).annotate(day=ExtractWeekDay('played_at')).values('day').annotate(
        plays=Count('id'),
        disputes=Count('id', filter=Q(flagged=True))
    )
    weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    daily_activity_data = [
        {"day": weekdays[r['day'] % 7], "plays": r['plays'], "disputes": r['disputes']}
        for r in da_qs
    ]

    payload = {
        "message": "Success",
        "data": {
            "dashboardType": "admin",
            "period": 'custom' if (sd_str and ed_str) else period,
            "start_date": sd_str,
            "end_date": ed_str,
            "platformStats": {
                "totalStations": total_stations,
                "totalArtists": total_artists,
                "totalSongs": total_songs,
                "totalPlays": total_plays,
                "totalRoyalties": total_royalties,
                "pendingPayments": pending_payments
            },
            "stationPerformance": station_performance,
            "topEarners": top_earners,
            "distributionMetrics": distribution_metrics,
            "revenueData": revenue_data,
            "genreData": genre_data,
            "dailyActivityData": daily_activity_data
        }
    }
    return Response(payload, status=status.HTTP_200_OK)


from django.core.cache import cache


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_dashboard_data_newwwwwwwwww(request):
    data = cache.get('admin_dashboard_data')
    if not data:
        return Response({"message": "Cache not ready, please try again."}, status=503)
    return Response({"message": "Success", "data": data}, status=200)
