
import os
import subprocess
import uuid
import shutil

from click import File
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
import librosa
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album, Artist, Contributor, Fingerprint, Genre, Track
from artists.serializers import AlbumSerializer, GenreSerializer
from django.core.files.base import ContentFile

from artists.utils.fingerprint_tracks import simple_fingerprint
from datetime import timedelta

from music_monitor.models import PlayLog
from django.utils import timezone
from django.db.models import Count, Sum
from datetime import datetime
from django.db.models import F
from django.db.models.functions import TruncDate, TruncMonth


User = get_user_model()




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_analytics_view(request):
    payload, data, errors = {}, {}, {}

    artist_id = request.query_params.get('artist_id')
    period = request.query_params.get('period', 'all-time')
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']
    else:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
        except Artist.DoesNotExist:
            errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Define timeframe by period
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
        return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    tracks = Track.objects.filter(artist=artist, is_archived=False)

    # Base queryset filtered by period
    base_qs = PlayLog.objects.filter(track__in=tracks)
    if start_date:
        base_qs = base_qs.filter(played_at__gte=start_date)

    # 1️⃣ Plays Over Time
    # If period suggests <= 30 days, group by day; else group by month
    if period in ('daily', 'weekly', 'monthly'):
        time_qs = (
            base_qs
            .annotate(day=TruncDate('played_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        playsOverTime = [
            {"date": entry['day'].strftime('%b %d'), "count": entry['count']}
            for entry in time_qs
        ]
    else:
        time_qs = (
            base_qs
            .annotate(month=TruncMonth('played_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        playsOverTime = [
            {"date": entry['month'].strftime('%b %Y'), "count": entry['count']}
            for entry in time_qs
        ]


    dummyPlaya22 = [
        { "date": "Jul 1", "count": 20 },
        { "date": "Jul 2", "count": 32 },
        { "date": "Jul 3", "count": 15 },
        { "date": "Jul 4", "count": 50 },
        { "date": "Jul 5", "count": 41 },
    ];


    # 2️⃣ Top Stations (by play count)
    station_totals = (
        base_qs
        .values(station_name=F('station__name'))
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    total_plays = sum(st['count'] for st in station_totals) or 1
    topStations = [
        {"name": st['station_name'], "percent": round(st['count'] * 100.0 / total_plays)}
        for st in station_totals[:3]
    ]
    others_pct = max(0, 100 - sum(s['percent'] for s in topStations))
    if others_pct > 0:
        topStations.append({"name": "Others", "percent": others_pct})

    # 3️⃣ Top Songs
    song_totals = (
        base_qs
        .values(title=F('track__title'))
        .annotate(count=Count('id'))
        .order_by('-count')[:4]
    )
    topSongs = [{"title": st['title'], "plays": st['count']} for st in song_totals]

    data.update({
        "period": period,
        "playsOverTime": playsOverTime,
        "topStations": topStations,
        # Temporary alias to match frontend expectation (setTopStations)
        "setTopStations": topStations,
        "topSongs": topSongs,
    })
    payload.update({"message": "Successful", "data": data})
    return Response(payload, status=status.HTTP_200_OK)
