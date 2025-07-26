from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Count, Avg, Sum, F
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status
import random
from django.db.models.functions import TruncDate

from music_monitor.models import PlayLog
from stations.models import Station



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_dashboard_data(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.query_params.get('station_id')
    period = request.query_params.get('period', 'all-time')
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')

    if not station_id:
        errors['station_id'] = ["Station ID is required"]

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ["Station does not exist"]

    # Date range filtering
    now = timezone.now()
    start_date = None
    end_date = None

    try:
        if start_date_str and end_date_str:
            start_date = timezone.make_aware(datetime.strptime(start_date_str, "%Y-%m-%d"))
            end_date = timezone.make_aware(datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1))
        else:
            if period == 'daily':
                start_date = now - timedelta(days=1)
            elif period == 'weekly':
                start_date = now - timedelta(days=7)
            elif period == 'monthly':
                start_date = now - timedelta(days=30)
            elif period == 'all-time':
                start_date = None
            else:
                errors['period'] = ['Invalid period. Choose from: daily, weekly, monthly, all-time']
    except ValueError:
        errors['date_format'] = ['start_date and end_date must be in YYYY-MM-DD format']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Fetch all logs for this station
    playlogs = PlayLog.objects.filter(station=station)

    if start_date and end_date:
        playlogs = playlogs.filter(played_at__range=(start_date, end_date))
    elif start_date:
        playlogs = playlogs.filter(played_at__gte=start_date)

    # Metrics
    totalSongs = playlogs.values('track').distinct().count()
    totalPlays = playlogs.count()

    # Top Songs
    top_songs_qs = (
        playlogs.values('track__title', 'track__artist__stage_name')
        .annotate(
            plays=Count('id'),
            confidence=Avg('avg_confidence_score')
        )
        .order_by('-plays')[:5]
    )

    topSongs = [
        {
            "title": song['track__title'],
            "artist": song['track__artist__stage_name'],
            "plays": song['plays'],
            "confidence": int(song['confidence'] or 0)
        }
        for song in top_songs_qs
    ]

    # Airplay by weekday
    weekday_map = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    airplay_qs = (
        playlogs.annotate(day_of_week=F('played_at__week_day'))
        .values('day_of_week')
        .annotate(plays=Count('id'))
    )

    plays_by_day = {i: 0 for i in range(1, 8)}
    for row in airplay_qs:
        plays_by_day[row['day_of_week']] = row['plays']

    airplayData = [
        {
            "day": weekday_map[i % 7],
            "plays": plays_by_day[i]
        } for i in range(1, 8)
    ]

    # Regional breakdown (by artist region)
    regional_qs = (
        playlogs.values('track__artist__region')
        .annotate(plays=Count('id'))
    )

    regionalData = [
        {
            "region": row['track__artist__region'] or "Unknown",
            "plays": row['plays'],
            "growth": round(random.uniform(5.0, 20.0), 1)
        }
        for row in regional_qs
    ]

    # Royalty calculations
    totalRoyalties = playlogs.aggregate(total=Sum('royalty_amount'))['total'] or 0

    # Dispute summary
    disputeSummary = {
        "total": playlogs.count(),
        "disputed": playlogs.filter(flagged=True).count(),
        "undisputed": playlogs.filter(flagged=False).count(),
    }

    station_name = station.name
    #####

    #Change Later

    ##########
    #######
    # Actual calculations
    confidence_score = playlogs.aggregate(avg_confidence=Avg('avg_confidence_score'))['avg_confidence'] or 0.0
    confidence_score = round(confidence_score, 1)

    active_regions = (
        playlogs
        .exclude(track__artist__region__isnull=True)
        .exclude(track__artist__region__exact='')
        .values('track__artist__region')
        .distinct()
        .count()
    )


    ###########

    trend_qs = (
        playlogs
        .annotate(date=TruncDate('played_at'))
        .values('date')
        .annotate(plays=Count('id'))
        .order_by('date')
        )

    trendData = [{"date": row["date"], "plays": row["plays"]} for row in trend_qs]



    # Final payload
    data.update({
        "period": period if not (start_date_str and end_date_str) else "custom",
        "start_date": start_date_str,
        "end_date": end_date_str,
        "stationName": station_name,
        "totalSongs": totalSongs,
        "totalPlays": totalPlays,
        "confidenceScore": confidence_score,
        "activeRegions": active_regions,
        "totalRoyalties": float(totalRoyalties),
        "topSongs": topSongs,
        "airplayData": airplayData,
        "regionalData": regionalData,
        "disputeSummary": disputeSummary,
        "trendData": trendData
    })

    payload['message'] = "Success"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)
