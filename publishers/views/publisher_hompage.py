
import random
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
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

from publishers.models import PublisherProfile
from music_monitor.models import PlayLog, StreamLog



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



User = get_user_model()



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_publisher_homedata(request):
    payload, data, errors = {}, {}, {}
    publisher_id = request.query_params.get('publisher_id')
    period = request.query_params.get('period', 'all-time')
    sd_str, ed_str = request.query_params.get('start_date'), request.query_params.get('end_date')

    if not publisher_id:
        errors['publisher_id'] = ["PublisherProfile ID is required"]
    try:
        publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['publisher_id'] = ['PublisherProfile does not exist']

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

    playlogs = PlayLog.objects.filter(track__publisher=publisher, active=True)
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
    fanlinks = StreamLog.objects.filter(track__publisher=publisher, active=True, fan__isnull=False)
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
        "publisherName": publisher.user.first_name,
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
