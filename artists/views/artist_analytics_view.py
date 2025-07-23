
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

from music_monitor.models import PlayLog, StreamLog
from django.utils import timezone
from django.db.models import Count, Sum
from datetime import datetime
from django.db.models import F


User = get_user_model()




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_analytics_view(request):
    payload, data, errors = {}, {}, {}

    artist_id = request.query_params.get('artist_id')
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

    # Define timeframe (last 7 days)
    today = timezone.now().date()
    week_ago = today - timedelta(days=6)

    tracks = Track.objects.filter(artist=artist, is_archived=False)

    # 1️⃣ Plays Over Time (past 7 days)
    plays_daily = (
        PlayLog.objects
        .filter(track__in=tracks, played_at__date__range=(week_ago, today))
        .extra({'date': "date(played_at)"})
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    dummyPlays = [
        {
            "date": datetime.strptime(entry['date'], "%Y-%m-%d").strftime("%b %d").lstrip("0").replace(" 0", " "),
            "count": entry['count']
        }
        for entry in plays_daily
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
        PlayLog.objects
        .filter(track__in=tracks)
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
        PlayLog.objects
        .filter(track__in=tracks)
        .values(title=F('track__title'))
        .annotate(count=Count('id'))
        .order_by('-count')[:4]
    )
    topSongs = [{"title": st['title'], "plays": st['count']} for st in song_totals]

    data.update({
        "playsOverTime": dummyPlays,
        "topStations": topStations,
        "topSongs": topSongs,
    })
    payload.update({"message": "Successful", "data": data})
    return Response(payload, status=status.HTTP_200_OK)