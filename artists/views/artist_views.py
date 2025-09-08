
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist, Contributor, Track
from bank_account.models import BankAccount
from core.utils import get_duration
from music_monitor.models import PlayLog

User = get_user_model()



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_artist(request):
    payload = {}
    data = {}
    errors = {}

    user_id = request.data.get('user_id', "")
    name = request.data.get('name', "").strip()
    stage_name = request.data.get('stage_name', "").strip()
    bio = request.data.get('bio', "")
    profile_image = request.data.get('profile_image', "")
    spotify_url = request.data.get('spotify_url', "")
    shazam_url = request.data.get('shazam_url', "")
    instagram = request.data.get('instagram', "")
    twitter = request.data.get('twitter', "")
    website = request.data.get('website', "")
    contact_email = request.data.get('contact_email', "")

    if not (stage_name or name):
        errors['stage_name'] = ['Stage name is required.']

    try:
        user = User.objects.get(user_id=user_id)
    except:
        errors['user_id'] = ['User ID does not exist.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    if not stage_name and name:
        stage_name = name

    artist = Artist.objects.create(
        user=user,
        stage_name=stage_name,
        bio=bio,
        profile_image=profile_image,
        spotify_url=spotify_url,
        shazam_url=shazam_url,
        instagram=instagram,
        twitter=twitter,
        website=website,
        contact_email=contact_email,
  
    )


    data["artist_id"] = artist.artist_id
    data["stage_name"] = artist.stage_name

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_201_CREATED)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artists_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_artists = Artist.objects.filter(is_archived=False)

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

    from ..serializers import AllArtistsSerializer 
    serializer = AllArtistsSerializer(paginated_artists, many=True)

    data['artists'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_artists.number,
        'total_pages': paginator.num_pages,
        'next': paginated_artists.next_page_number() if paginated_artists.has_next() else None,
        'previous': paginated_artists.previous_page_number() if paginated_artists.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_details_view(request):
    payload = {}
    data = {}
    errors = {}

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

    from ..serializers import ArtistSerializer
    serializer = ArtistSerializer(artist)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_artist(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fields_to_update = [
        'stage_name', 'bio', 'profile_image', 'spotify_url',
        'shazam_url', 'instagram', 'twitter', 'website', 'contact_email', 'active'
    ]
    for field in fields_to_update:
        value = request.data.get(field)
        if value is not None:
            setattr(artist, field, value)

    artist.save()

    data["artist_id"] = artist.id
    data["stage_name"] = artist.stage_name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_artist(request):
    payload = {}
    errors = {}

    artist_id = request.data.get('artist_id')
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    artist.is_archived = True
    artist.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_artist(request):
    payload = {}
    errors = {}

    artist_id = request.data.get('artist_id')
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    artist.is_archived = False
    artist.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_artist(request):
    payload = {}
    errors = {}

    artist_id = request.data.get('artist_id')
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    artist.delete()
    payload['message'] = "Deleted successfully"
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_artists_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_artists = Artist.objects.filter(is_archived=True)

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

    from ..serializers import ArtistSerializer  # Make sure you have this
    serializer = ArtistSerializer(paginated_artists, many=True)

    data['artists'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_artists.number,
        'total_pages': paginator.num_pages,
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
def get_artist_profile_view(request):
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
        "totalPlays": PlayLog.objects.filter(track__in=tracks).count(),
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
        plays_count = PlayLog.objects.filter(track=t).count()
        earnings = (PlayLog.objects.filter(track=t).aggregate(Sum('royalty_amount'))['royalty_amount__sum'] or 0)
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
            "contributors": [{
                "name": (f"{(c.user.first_name or '')} {(c.user.last_name or '')}".strip() or c.user.username or c.user.email),
                "role": c.role,
                "percentage": float(c.percent_split)
            } for c in contributors],
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

    # Royalty history (radio only)
    radio_logs = PlayLog.objects.filter(track__in=tracks).order_by('-played_at')[:10]
    royaltyHistory = [{
        "date": log.played_at.strftime("%Y-%m-%d"),
        "amount": float(log.royalty_amount or 0),
        "source": "Radio Airplay",
        "status": "Paid" if getattr(log, 'claimed', False) else "Pending"
    } for log in radio_logs]

    # Recent play logs combined
    playlogs_qs = PlayLog.objects.filter(track__in=tracks).order_by('-played_at')[:5]
    playLogs = [
        {
            "id": log.id,
            "song": log.track.title,
            "station": log.station.name,
            "date": log.played_at.strftime("%Y-%m-%d %H:%M"),
            "duration": str(get_duration(log.duration)) if log.duration else None,
            "earnings": float(log.royalty_amount or 0)
        } for log in playlogs_qs
    ]

    data.update({
        "artistData": artistData,
        "songs": songs,
        "royaltyHistory": royaltyHistory,
        "playLogs": playLogs
    })

    # Publisher info (artist-level)
    publisher = getattr(artist, 'publisher', None)
    if publisher:
        publisherInfo = {
            "companyName": publisher.company_name,
            "verified": publisher.verified,
            "writerSplit": float(publisher.writer_split or 0),
            "publisherSplit": float(publisher.publisher_split or 0),
            "location": "{}{}{}".format(
                f"{publisher.city}, " if publisher.city else "",
                f"{publisher.region}, " if publisher.region else "",
                publisher.country or ""
            ).strip().strip(', '),
        }
    else:
        publisherInfo = {
            "companyName": None,
            "verified": False,
            "writerSplit": 0.0,
            "publisherSplit": 0.0,
            "location": "",
        }

    publisherInfo["selfPublished"] = bool(getattr(artist, 'self_publish', False))
    data["publisherInfo"] = publisherInfo

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)
