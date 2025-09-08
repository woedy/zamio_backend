
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist, Contributor, Track
from artists.serializers import AllArtistsSerializer
from bank_account.models import BankAccount
from core.utils import get_duration
from music_monitor.models import PlayLog, StreamLog

User = get_user_model()






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_managed_artists_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    # Only artists linked to the current publisher
    from publishers.models import PublisherProfile
    publisher = None
    publisher_id = request.query_params.get('publisher_id')
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
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    all_artists = Artist.objects.filter(is_archived=False, publisher=publisher)

    if search_query:
        all_artists = all_artists.filter(
            Q(stage_name__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    paginator = Paginator(all_artists, page_size)
    try:
        paginated_artists = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_artists = paginator.page(1)
    except EmptyPage:
        paginated_artists = paginator.page(paginator.num_pages)

    serializer = AllArtistsSerializer(paginated_artists, many=True)

    data['artists'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_artists.number,
        'total_pages': paginator.num_pages,
        'count': paginator.count,
        'next': paginated_artists.next_page_number() if paginated_artists.has_next() else None,
        'previous': paginated_artists.previous_page_number() if paginated_artists.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)




from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from django.db.models import Sum, Count, Q, F

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_managed_artist_details_view(request):
    payload, data, errors = {}, {}, {}

    artist_id = request.query_params.get('artist_id')
    if not artist_id:
        errors['artist_id'] = ["Artist ID is required"]
    else:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
        except Artist.DoesNotExist:
            errors['artist_id'] = ["Artist does not exist"]

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    tracks = Track.objects.filter(artist=artist, is_archived=False)

    # Artist info
    artistData = {
        "name": f"{artist.user.first_name or ''} {artist.user.last_name or ''}".strip(),
        "stageName": artist.stage_name,
        "bio": artist.bio,
        "avatar": artist.user.photo.url if artist.user.photo else None,
        "coverImage": None,
        "verified": artist.verified,
        "followers": artist.followers.count(),
        "totalPlays": PlayLog.objects.filter(track__in=tracks).count() + StreamLog.objects.filter(track__in=tracks).count(),
        "totalEarnings": float(BankAccount.objects.filter(user=artist.user).aggregate(Sum('balance'))['balance__sum'] or 0),
        "joinDate": artist.created_at.date().isoformat(),
        "location": artist.location_name or f"{artist.city}, {artist.country}" if hasattr(artist, 'country') else "",
        "genres": list(artist.artist_genre.filter(is_archived=False).values_list('genre__name', flat=True).distinct()),
        "contact": {
            "email": artist.contact_email,
            "phone": artist.user.phone,
            "instagram": artist.instagram,
            "twitter": artist.twitter,
            "facebook": None,
        }
    }

    # Songs list
    songs = []
    for t in tracks:
        plays_count = PlayLog.objects.filter(track=t).count() + StreamLog.objects.filter(track=t).count()
        earnings = (PlayLog.objects.filter(track=t).aggregate(Sum('royalty_amount'))['royalty_amount__sum'] or 0) + \
                   (StreamLog.objects.filter(track=t).aggregate(Sum('royalty_amount'))['royalty_amount__sum'] or 0)
        contributors = Contributor.objects.filter(track=t, is_archived=False)
        songs.append({
            "id": t.id,
            "title": t.title,
            "duration": str(t.duration) if t.duration else None,
            "releaseDate": t.release_date.isoformat() if t.release_date else None,
            "totalPlays": plays_count,
            "totalEarnings": float(earnings),
            "status": "Active" if t.active else "Inactive",
            "album": t.album.title if t.album else None,
            "genre": t.genre.name if t.genre else None,
            "contributors": [{"name": c.name, "role": c.role, "percentage": float(c.percent_split)} for c in contributors],
            "recentPlays": [
                {
                    "station": log.station.name,
                    "date": log.played_at.strftime("%Y-%m-%d"),
                    "plays": 1,
                    "earnings": float(log.royalty_amount or 0)
                }
                for log in PlayLog.objects.filter(track=t).order_by('-played_at')[:3]
            ]
        })

    # Royalty history (mix of radio & streaming with status via transaction or claimed flag)
    radio_logs = PlayLog.objects.filter(track__in=tracks).order_by('-played_at')[:10]
    streaming_logs = StreamLog.objects.filter(track__in=tracks).order_by('-played_at')[:10]
    royaltyHistory = []
    for log in radio_logs:
        royaltyHistory.append({
            "date": log.played_at.strftime("%Y-%m-%d"),
            "amount": float(log.royalty_amount or 0),
            "source": "Radio Airplay",
            "status": "Paid" if log.claimed else "Pending"
        })
    for log in streaming_logs:
        royaltyHistory.append({
            "date": log.played_at.strftime("%Y-%m-%d"),
            "amount": float(log.royalty_amount or 0),
            "source": "Streaming",
            "status": "Paid" if log.claimed else "Pending"
        })
    royaltyHistory = sorted(royaltyHistory, key=lambda x: x['date'], reverse=True)[:10]

    # Recent play logs combined
    playlogs_qs = PlayLog.objects.filter(track__in=tracks).order_by('-played_at')[:5]
    playLogs = [
        {
            "id": log.id,
            "song": log.track.title,
            "station": log.station.name,
            "date": log.played_at.strftime("%Y-%m-%d %H:%M"),
            "duration": str(get_duration(log.duration)) if log.duration else None,
            "confidence": float(log.avg_confidence_score or 0),
            "earnings": float(log.royalty_amount or 0)
        } for log in playlogs_qs
    ]

    data.update({
        "artistData": artistData,
        "songs": songs,
        "royaltyHistory": royaltyHistory,
        "playLogs": playLogs
    })

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


