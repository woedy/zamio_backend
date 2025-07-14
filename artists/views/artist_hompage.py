
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
from music_monitor.models import PlayLog

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




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_homedata(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.query_params.get('artist_id')
    period = request.query_params.get('period', 'all-time')
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')

    if not artist_id:
        errors['artist_id'] = ["Artist ID is required"]

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist does not exist']

    # Determine time filter
    now = timezone.now()
    start_date = None
    end_date = None

    try:
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = timezone.make_aware(end_date + timedelta(days=1))  # include full end day
            start_date = timezone.make_aware(start_date)
        else:
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
    except ValueError:
        errors['date_format'] = ['start_date and end_date must be in YYYY-MM-DD format']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Filter play logs by artist and date range
    playlogs = PlayLog.objects.filter(track__artist=artist, active=True)
    if start_date and end_date:
        playlogs = playlogs.filter(played_at__range=(start_date, end_date))
    elif start_date:
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

    # Plays Over Time (monthly or daily depending on range)
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

    # Fan Demographics (static)
    _fan_demographics = [
        {"ageGroup": "18-24", "percentage": 35, "color": "from-purple-500 to-pink-500"},
        {"ageGroup": "25-34", "percentage": 28, "color": "from-blue-500 to-purple-500"},
        {"ageGroup": "35-44", "percentage": 20, "color": "from-green-500 to-blue-500"},
        {"ageGroup": "45-54", "percentage": 12, "color": "from-yellow-500 to-green-500"},
        {"ageGroup": "55+", "percentage": 5, "color": "from-orange-500 to-yellow-500"}
    ]

    # Final response data
    data['period'] = period if not (start_date_str and end_date_str) else 'custom'
    data['start_date'] = start_date_str
    data['end_date'] = end_date_str
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