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

from artists.models import Artist, PlatformAvailability, Track, Genre
from music_monitor.models import PlayLog
from stations.models import Station
from activities.models import AllActivity

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

    # Monthly growth (royalties): last 30 days vs previous 30 days
    last_30 = now - timedelta(days=30)
    prev_60 = now - timedelta(days=60)
    last_sum = float(PlayLog.objects.filter(active=True, played_at__gte=last_30).aggregate(s=Sum('royalty_amount'))['s'] or 0)
    prev_sum = float(PlayLog.objects.filter(active=True, played_at__gte=prev_60, played_at__lt=last_30).aggregate(s=Sum('royalty_amount'))['s'] or 0)
    if prev_sum > 0:
        monthly_growth = round(((last_sum - prev_sum) / prev_sum) * 100.0, 1)
    else:
        monthly_growth = 0.0

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

    # Revenue and new artists per month (last 6 months)
    revenue_data = []
    months_back = 6
    for i in range(months_back - 1, -1, -1):
        start_m = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        end_m = (start_m + timedelta(days=32)).replace(day=1)
        start_m = timezone.make_aware(start_m) if timezone.is_naive(start_m) else start_m
        end_m = timezone.make_aware(end_m) if timezone.is_naive(end_m) else end_m
        rev = PlayLog.objects.filter(active=True, played_at__gte=start_m, played_at__lt=end_m).aggregate(s=Sum('royalty_amount'))['s'] or 0
        new_artists = Artist.objects.filter(created_at__gte=start_m, created_at__lt=end_m).count()
        revenue_data.append({
            "month": start_m.strftime('%Y-%m'),
            "revenue": float(rev),
            "artists": new_artists,
        })

    # Genre breakdown with colors
    genre_qs = Track.objects.filter(track_playlog__active=True).values('genre__name', 'genre__color').annotate(
        plays=Count('track_playlog')
    )
    # Fallback palette
    palette = ['#8B5CF6', '#EC4899', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#84CC16']
    genre_data = []
    for idx, r in enumerate(genre_qs):
        name = r['genre__name'] or "Unknown"
        color = r['genre__color'] or palette[idx % len(palette)]
        genre_data.append({"name": name, "value": r['plays'], "color": color})

    # Daily activity counts (last week): registrations, payments proxy (plays), disputes
    last_week = now - timedelta(days=7)
    # Build a map for each weekday to default 0s
    weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    counts_map = {i: {"registrations": 0, "payments": 0, "disputes": 0} for i in range(7)}
    # Registrations by day
    regs = Artist.objects.filter(created_at__gte=last_week).annotate(day=ExtractWeekDay('created_at')).values('day').annotate(c=Count('id'))
    for r in regs:
        counts_map[r['day'] % 7]["registrations"] = r['c']
    # Payments proxy by day (plays revenue)
    pays = PlayLog.objects.filter(active=True, played_at__gte=last_week).annotate(day=ExtractWeekDay('played_at')).values('day').annotate(c=Count('id'))
    for r in pays:
        counts_map[r['day'] % 7]["payments"] = r['c']
    # Disputes by day
    disp = PlayLog.objects.filter(active=True, flagged=True, played_at__gte=last_week).annotate(day=ExtractWeekDay('played_at')).values('day').annotate(c=Count('id'))
    for r in disp:
        counts_map[r['day'] % 7]["disputes"] = r['c']
    daily_activity_data = [
        {"day": weekdays[i], **counts_map[i]} for i in range(7)
    ]

    # Recent activity feed (last 10)
    recent_activity = []
    acts = AllActivity.objects.order_by('-timestamp')[:10]
    for a in acts:
        recent_activity.append({
            "id": a.id,
            "type": (a.type or 'activity').lower(),
            "description": a.subject or a.body or 'Activity',
            "time": a.timestamp.strftime('%Y-%m-%d %H:%M'),
            "status": 'completed',
        })


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
                "pendingPayments": pending_payments,
                "monthlyGrowth": monthly_growth,
            },
            "stationPerformance": [
                {
                    "name": r["station"],
                    "plays": r["plays"],
                    "revenue": r["revenue"],
                    "compliance": 95,
                    "status": "active",
                }
                for r in station_performance
            ],
            "topEarners": [
                {**r, "growth": random.randint(1, 20)} for r in top_earners
            ],
            "distributionMetrics": [
                {**r, "growth": random.randint(1, 25)} for r in distribution_metrics
            ],
            "revenueData": revenue_data,
            "genreData": genre_data,
            "dailyActivityData": daily_activity_data,
            "recentActivity": recent_activity,
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
