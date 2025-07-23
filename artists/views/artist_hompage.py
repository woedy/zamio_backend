
import random
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta, datetime

from django.db.models import Sum, Count, Avg, F, Q
from collections import defaultdict
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication

from artists.models import Artist
from music_monitor.models import PlayLog, StreamLog

User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_homedata2222222(request):
    payload = {}
    data = {}
    errors = {}
    data = {}

    artist_id = request.query_params.get('artist_id')

    if not artist_id:
        errors['artist_id'] = ["Artist ID is required"]

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist does not exist']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    

    totalPlays = 0
    totalStations = 0
    totalEarnings = 0
    streamingPlays = 0

    # Top Songs
    _top_songs = []
    
    data['topSongs'] = _top_songs


    # Top PlayOverTime
    _play_over_time = []
    
    data['playsOverTime'] = _play_over_time
    

    # Top Ghana Regions
    _ghana_regioins = []
    
    data['ghanaRegions'] = _ghana_regioins

    # Fan Demographics
    _fan_demographics = []
    
    data['funDemographics'] = _fan_demographics
    


    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_homedata3333(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.query_params.get('artist_id')
    period = request.query_params.get('period', 'all-time')  # Optional period filter

    if not artist_id:
        errors['artist_id'] = ["Artist ID is required"]

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist does not exist']

    # Validate period
    now = timezone.now()
    start_date = None

    if period == 'daily':
        start_date = now - timedelta(days=1)
    elif period == 'weekly':
        start_date = now - timedelta(weeks=1)
    elif period == 'monthly':
        start_date = now - timedelta(days=30)
    elif period == 'all-time':
        start_date = None
    else:
        errors['period'] = ['Invalid period. Choose from: daily, weekly, monthly, all-time']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Filter play logs by artist and period
    playlogs = PlayLog.objects.filter(track__artist=artist, active=True)
    if start_date:
        playlogs = playlogs.filter(played_at__gte=start_date)

    # Aggregates
    totalPlays = playlogs.count()
    totalStations = playlogs.values('station').distinct().count()
    totalEarnings = playlogs.aggregate(total=Sum('royalty_amount'))['total'] or 0
    streamingPlays = playlogs.filter(source='Streaming').count()

    # Top Songs
    top_tracks = (
        playlogs.values('track__id', 'track__title')
        .annotate(
            plays=Count('id'),
            earnings=Sum('royalty_amount'),
            confidence=Avg('avg_confidence_score'),
            stations=Count('station', distinct=True)
        )
        .order_by('-plays')[:5]
    )

    _top_songs = []
    for track in top_tracks:
        _top_songs.append({
            "title": track['track__title'],
            "plays": track['plays'],
            "earnings": round(track['earnings'] or 0, 2),
            "confidence": int(track['confidence'] or 0),
            "stations": track['stations'],
        })

    # Plays Over Time (by month)
    plays_by_month = (
        playlogs.annotate(month=F('played_at__month'))
        .values('month')
        .annotate(airplay=Count('id'))
        .order_by('month')
    )

    _play_over_time = []
    month_map = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for month_data in plays_by_month:
        _play_over_time.append({
            'date': month_map[month_data['month'] - 1],
            'airplay': month_data['airplay'],
            'streaming': playlogs.filter(
                source='Streaming',
                played_at__month=month_data['month']
            ).count()
        })

    # Ghana Region Breakdown
    station_plays = playlogs.values('station__region').annotate(
        plays=Count('id'),
        earnings=Sum('royalty_amount'),
        stations=Count('station', distinct=True)
    )

    _ghana_regions = []
    for region in station_plays:
        _ghana_regions.append({
            "region": region['station__region'] or "Unknown",
            "plays": region['plays'],
            "earnings": round(region['earnings'] or 0, 2),
            "stations": region['stations'],
            "growth": round(random.uniform(5.0, 20.0), 1)  # Placeholder
        })

    # Fan Demographics (static for now)
    _fan_demographics = [
        {"ageGroup": "18-24", "percentage": 35, "color": "from-purple-500 to-pink-500"},
        {"ageGroup": "25-34", "percentage": 28, "color": "from-blue-500 to-purple-500"},
        {"ageGroup": "35-44", "percentage": 20, "color": "from-green-500 to-blue-500"},
        {"ageGroup": "45-54", "percentage": 12, "color": "from-yellow-500 to-green-500"},
        {"ageGroup": "55+", "percentage": 5, "color": "from-orange-500 to-yellow-500"}
    ]

    # Construct data payload
    data['period'] = period
    data['totalPlays'] = totalPlays
    data['totalStations'] = totalStations
    data['totalEarnings'] = round(totalEarnings, 2)
    data['streamingPlays'] = streamingPlays
    data['topSongs'] = _top_songs
    data['playsOverTime'] = _play_over_time
    data['ghanaRegions'] = _ghana_regions
    data['fanDemographics'] = _fan_demographics

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)



from datetime import datetime, timedelta
import random
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from django.db.models.functions import ExtractYear, TruncDate, TruncMonth
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_homedata(request):
    payload, data, errors = {}, {}, {}
    artist_id = request.query_params.get('artist_id')
    period = request.query_params.get('period', 'all-time')
    sd_str, ed_str = request.query_params.get('start_date'), request.query_params.get('end_date')

    if not artist_id:
        errors['artist_id'] = ["Artist ID is required"]
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist does not exist']

    now = timezone.now()
    start_date = end_date = None

    try:
        if sd_str and ed_str:
            s = datetime.strptime(sd_str, '%Y-%m-%d')
            e = datetime.strptime(ed_str, '%Y-%m-%d') + timedelta(days=1)
            start_date = timezone.make_aware(s)
            end_date = timezone.make_aware(e)
        else:
            mapping = {
                'daily': now - timedelta(days=1),
                'weekly': now - timedelta(weeks=1),
                'monthly': now - timedelta(days=30),
                'all-time': None
            }
            if period in mapping:
                start_date = mapping[period]
            else:
                errors['period'] = ['Invalid period. Choose from: daily, weekly, monthly, all-time']
    except ValueError:
        errors['date_format'] = ['start_date and end_date must be YYYY-MM-DD']

    if errors:
        return Response({'message': "Errors", 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    playlogs = PlayLog.objects.filter(track__artist=artist, active=True)
    if start_date:
        if end_date:
            playlogs = playlogs.filter(played_at__range=(start_date, end_date))
        else:
            playlogs = playlogs.filter(played_at__gte=start_date)

    totalPlays = playlogs.count()
    totalStations = playlogs.values('station').distinct().count()
    totalEarnings = playlogs.aggregate(total=Sum('royalty_amount'))['total'] or 0
    streamingPlays = playlogs.filter(source='Streaming').count()
    confidence_score = playlogs.aggregate(avg=Avg('avg_confidence_score'))['avg'] or 0
    active_regions = playlogs.values('station__region').exclude(station__region__isnull=True).distinct().count()

    # Top Songs
    top_tracks = (
        playlogs.values('track__title')
        .annotate(
            plays=Count('id'),
            earnings=Sum('royalty_amount'),
            confidence=Avg('avg_confidence_score'),
            stations=Count('station', distinct=True)
        )
        .order_by('-plays')[:5]
    )
    topSongs = [{
        "title": t['track__title'],
        "plays": t['plays'],
        "earnings": round(t['earnings'] or 0, 2),
        "confidence": int(t['confidence'] or 0),
        "stations": t['stations']
    } for t in top_tracks]

    # Plays Over Time
    duration_days = (end_date - start_date).days if start_date and end_date else None
    if duration_days and duration_days <= 30:
        tb = TruncDate('played_at')
        time_qs = playlogs.annotate(date=tb).values('date').annotate(airplay=Count('id')).order_by('date')
    else:
        tb = TruncMonth('played_at')
        time_qs = playlogs.annotate(date=tb).values('date').annotate(airplay=Count('id')).order_by('date')

    playsOverTime = [
        {
            'date': entry['date'].strftime('%Y-%m-%d'),
            'airplay': entry['airplay'],
            'streaming': playlogs.filter(source='Streaming', played_at__date=entry['date'].date() if hasattr(entry['date'], 'date') else entry['date'].date()).count()
        }
        for entry in time_qs
    ]

    # Ghana Region Breakdown
    region_qs = playlogs.values('station__region').annotate(
        plays=Count('id'), earnings=Sum('royalty_amount'), stations=Count('station', distinct=True)
    )
    ghanaRegions = [{
        "region": r['station__region'] or "Unknown",
        "plays": r['plays'],
        "earnings": round(r['earnings'] or 0, 2),
        "stations": r['stations'],
        "growth": round(random.uniform(5.0, 20.0), 1)
    } for r in region_qs]

    # Station Breakdown
    sb_qs = playlogs.values('station__name', 'station__region').annotate(plays=Count('id')).order_by('-plays')
    station_total = totalPlays or 1
    stationBreakdown = [{
        "station": s['station__name'],
        "plays": s['plays'],
        "percentage": round((s['plays'] / station_total) * 100, 1),
        "region": s['station__region'] or "Unknown"
    } for s in sb_qs[:5]]
    others = sb_qs[5:]
    if others:
        others_total = sum([o['plays'] for o in others])
        stationBreakdown.append({
            "station": "Others",
            "plays": others_total,
            "percentage": round((others_total / station_total) * 100, 1),
            "region": "Various"
        })

    # Fan Demographics
    fanlinks = StreamLog.objects.filter(track__artist=artist, active=True, fan__isnull=False)
    fan_age = fanlinks.annotate(age=timezone.now().year - ExtractYear('fan__dob'))
    total_fans = fan_age.values('fan').distinct().count() or 1
    buckets = {
        "18-24": Q(age__gte=18, age__lte=24),
        "25-34": Q(age__gte=25, age__lte=34),
        "35-44": Q(age__gte=35, age__lte=44),
        "45-54": Q(age__gte=45, age__lte=54),
        "55+": Q(age__gte=55),
    }
    fanDemographics = [{
        "ageGroup": label,
        "percentage": round((fan_age.filter(cond).values('fan').distinct().count() / total_fans) * 100, 1),
    } for label, cond in buckets.items()]

    # Performance Score
    overall = round((confidence_score / 100) * 10, 1)
    lookback = duration_days if duration_days else 7
    prev_plays = playlogs.filter(played_at__range=(start_date - timedelta(days=lookback), start_date)).count() if start_date else 0
    growth = round(((totalPlays - prev_plays) / prev_plays * 100), 1) if prev_plays else 100.0
    unique_fans = fanlinks.values('fan').distinct().count()
    fan_engagement = round((totalPlays / (unique_fans or 1)), 1)
    performanceScore = {
        "overall": overall,
        "airplayGrowth": growth,
        "RegionalReach": active_regions,
        "fanEngagement": fan_engagement
    }

    data.update({
        "period": 'custom' if sd_str and ed_str else period,
        "start_date": sd_str,
        "end_date": ed_str,
        "artistName": artist.stage_name,
        "totalPlays": totalPlays,
        "totalStations": totalStations,
        "totalEarnings": round(totalEarnings, 2),
        "streamingPlays": streamingPlays,
        "confidenceScore": round(confidence_score, 1),
        "activeRegions": active_regions,
        "topSongs": topSongs,
        "playsOverTime": playsOverTime,
        "ghanaRegions": ghanaRegions,
        "stationBreakdown": stationBreakdown,
        "fanDemographics": fanDemographics,
        "performanceScore": performanceScore
    })

    return Response({"message": "Successful", "data": data}, status=status.HTTP_200_OK)
