
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album, Artist, Genre, Track

User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_track(request):
    payload = {}
    data = {}
    errors = {}

    title = request.data.get('title', "")
    artist_id = request.data.get('artist_id', "")
    album_id = request.data.get('album_id', "")
    release_date = request.data.get('release_date', "")
    isrc_code = request.data.get('isrc_code', "")
    genre_id = request.data.get('genre_id', "")
    lyrics = request.data.get('lyrics', "")
    explicit = request.data.get('explicit', False)
    audio_file = request.FILES.get('audio_file', None)

    if not title:
        errors['title'] = ['Track title is required.']
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']
    if not release_date:
        errors['release_date'] = ['Release date is required.']
    if not isrc_code:
        errors['isrc_code'] = ['ISRC code is required.']
    elif Track.objects.filter(isrc_code=isrc_code).exists():
        errors['isrc_code'] = ['ISRC code already exists.']
    if not genre_id:
        errors['genre_id'] = ['Genre is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    album = None
    if album_id:
        try:
            album = Album.objects.get(id=album_id)
        except Album.DoesNotExist:
            errors['album'] = ['Album not found.']

    try:
        genre = Genre.objects.get(id=genre_id)
    except Genre.DoesNotExist:
        errors['genre'] = ['Genre not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    track = Track.objects.create(
        title=title,
        artist=artist,
        album=album,
        release_date=release_date,
        isrc_code=isrc_code,
        genre=genre,
        lyrics=lyrics,
        explicit=explicit,
        audio_file=audio_file,
        active=True
    )

    data['track_id'] = track.id
    data['title'] = track.title
    data['isrc_code'] = track.isrc_code

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)







@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_tracks_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    tracks = Track.objects.filter(is_archived=False)

    if search_query:
        tracks = tracks.filter(
            Q(title__icontains=search_query) |
            Q(isrc_code__icontains=search_query) |
            Q(artist__name__icontains=search_query) |
            Q(album__title__icontains=search_query)
        )

    paginator = Paginator(tracks, page_size)
    try:
        paginated_tracks = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_tracks = paginator.page(1)
    except EmptyPage:
        paginated_tracks = paginator.page(paginator.num_pages)

    from ..serializers import TrackSerializer
    serializer = TrackSerializer(paginated_tracks, many=True)

    data['tracks'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_tracks.number,
        'total_pages': paginator.num_pages,
        'next': paginated_tracks.next_page_number() if paginated_tracks.has_next() else None,
        'previous': paginated_tracks.previous_page_number() if paginated_tracks.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_track_details_view(request):
    payload = {}
    errors = {}

    track_id = request.query_params.get('track_id')

    if not track_id:
        errors['track_id'] = ['Track ID is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import TrackSerializer
    serializer = TrackSerializer(track, many=False)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_track(request):
    payload = {}
    data = {}
    errors = {}

    track_id = request.data.get('track_id')

    if not track_id:
        errors['track_id'] = ['Track ID is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Update optional fields
    for field in ['title', 'release_date', 'lyrics', 'explicit', 'file_path']:
        val = request.data.get(field, None)
        if val is not None:
            setattr(track, field, val)

    new_audio = request.FILES.get('audio_file', None)
    if new_audio:
        track.audio_file = new_audio

    artist_id = request.data.get('artist_id', None)
    if artist_id:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
            track.artist = artist
        except Artist.DoesNotExist:
            errors['artist'] = ['Artist not found.']

    album_id = request.data.get('album_id', None)
    if album_id:
        try:
            album = Album.objects.get(id=album_id)
            track.album = album
        except Album.DoesNotExist:
            errors['album'] = ['Album not found.']

    genre_id = request.data.get('genre_id', None)
    if genre_id:
        try:
            genre = Genre.objects.get(id=genre_id)
            track.genre = genre
        except Genre.DoesNotExist:
            errors['genre'] = ['Genre not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    track.save()

    data['track_id'] = track.id
    data['title'] = track.title

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_track(request):
    return toggle_track_archive_state(request, True)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_track(request):
    return toggle_track_archive_state(request, False)


def toggle_track_archive_state(request, state):
    payload = {}
    errors = {}

    track_id = request.data.get('track_id', "")

    if not track_id:
        errors['track_id'] = ['Track ID is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    track.is_archived = state
    track.save()

    payload['message'] = "Successful"
    return Response(payload)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_track(request):
    payload = {}
    errors = {}

    track_id = request.data.get('track_id', "")

    if not track_id:
        errors['track_id'] = ['Track ID is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    track.delete()

    payload['message'] = "Track deleted successfully."
    return Response(payload)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_tracks_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    tracks = Track.objects.filter(is_archived=True)

    if search_query:
        tracks = tracks.filter(
            Q(title__icontains=search_query) |
            Q(isrc_code__icontains=search_query) |
            Q(artist__name__icontains=search_query)
        )

    paginator = Paginator(tracks, page_size)
    try:
        paginated_tracks = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_tracks = paginator.page(1)
    except EmptyPage:
        paginated_tracks = paginator.page(paginator.num_pages)

    from ..serializers import TrackSerializer
    serializer = TrackSerializer(paginated_tracks, many=True)

    data['tracks'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_tracks.number,
        'total_pages': paginator.num_pages,
        'next': paginated_tracks.next_page_number() if paginated_tracks.has_next() else None,
        'previous': paginated_tracks.previous_page_number() if paginated_tracks.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
