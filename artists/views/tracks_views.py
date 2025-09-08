
import os
import subprocess
import uuid
import shutil
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate, TruncMonth

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

from core.utils import get_duration
from music_monitor.models import PlayLog


User = get_user_model()





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_track(request):
    data = {}
    errors = {}

    title = request.data.get('title', "").strip()
    artist_id = request.data.get('artist_id', "").strip()
    album_id = request.data.get('album_id', "").strip()
    release_date = request.data.get('release_date', "").strip()
    genre_id = request.data.get('genre_id', "").strip()
    lyrics = request.data.get('lyrics', "")
    explicit = request.data.get('explicit', False)
    audio_file_uploaded = request.FILES.get('audio_file', None)

    # Validate required fields
    if not title:
        errors['title'] = ['Track title is required.']
    if not genre_id:
        errors['genre_id'] = ['Genre is required.']
    if not audio_file_uploaded:
        errors['audio_file'] = ['Audio file is required.']

    # Validate artist
    artist = None
    if artist_id:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
        except Artist.DoesNotExist:
            errors['artist'] = ['Artist not found.']
    else:
        errors['artist_id'] = ['Artist ID is required.']

    # Validate album (optional)
    album = None
    if album_id:
        try:
            album = Album.objects.get(id=album_id)
        except Album.DoesNotExist:
            errors['album'] = ['Album not found.']

    # Validate genre
    genre = None
    if genre_id:
        try:
            genre = Genre.objects.get(id=genre_id)
        except Genre.DoesNotExist:
            errors['genre'] = ['Genre not found.']

    # Return early if validation failed
    if errors:
        return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    # Prepare temp paths and filenames
    original_ext = os.path.splitext(audio_file_uploaded.name)[1].lower()
    base_filename = uuid.uuid4().hex
    mp3_name = f"{base_filename}.mp3"
    wav_name = f"{base_filename}.wav"

    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
    os.makedirs(temp_dir, exist_ok=True)

    input_path = os.path.join(temp_dir, f"{base_filename}{original_ext}")
    wav_path = os.path.join(temp_dir, wav_name)
    mp3_path = os.path.join(temp_dir, mp3_name)

    # Save uploaded file to input_path
    try:
        with open(input_path, 'wb+') as dest:
            for chunk in audio_file_uploaded.chunks():
                dest.write(chunk)
    except Exception as e:
        errors['audio_file'] = [f'Failed to save uploaded file: {str(e)}']
        return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    track = None

    try:
        # Create track without audio files first
        track = Track.objects.create(
            title=title,
            artist=artist,
            album=album,
            release_date=release_date or None,
            genre=genre,
            lyrics=lyrics,
            explicit=explicit,
            active=True
        )

        # Convert or copy to both formats
        if original_ext == '.mp3':
            subprocess.run(['ffmpeg', '-i', input_path, '-ar', '44100', '-ac', '2', '-f', 'wav', wav_path], check=True)
            if input_path != mp3_path:
                shutil.copyfile(input_path, mp3_path)
            else:
                # Just use the input_path as the mp3_path
                mp3_path = input_path

        elif original_ext == '.wav':
            subprocess.run(['ffmpeg', '-i', input_path, '-b:a', '192k', mp3_path], check=True)
            # If the uploaded file is already WAV at the desired path, skip copying
            if input_path != wav_path:
                shutil.copyfile(input_path, wav_path)

        else:
            raise ValueError("Unsupported file type. Only .mp3 and .wav are supported.")

        # Load audio and extract duration
        clip_samples, clip_sr = librosa.load(wav_path, sr=None)
        duration_seconds = librosa.get_duration(y=clip_samples, sr=clip_sr)
        track.duration = timedelta(seconds=round(duration_seconds))

        # Generate fingerprints
        audio_fingerprints = simple_fingerprint(clip_samples, clip_sr, plot=False)

        # Save both audio formats to Track model
        with open(wav_path, 'rb') as wav_file, open(mp3_path, 'rb') as mp3_file:
            wav_django_file = ContentFile(wav_file.read())
            mp3_django_file = ContentFile(mp3_file.read())

            track.audio_file_wav.save(wav_name, wav_django_file, save=False)
            track.audio_file_mp3.save(mp3_name, mp3_django_file, save=False)
            track.fingerprinted = True
            track.save()

        # Save fingerprints
        if audio_fingerprints:
            fingerprint_objects = [
                Fingerprint(track=track, hash=hash_value, offset=offset)
                for hash_value, offset in audio_fingerprints
            ]
            Fingerprint.objects.bulk_create(fingerprint_objects, batch_size=1000)

    except subprocess.CalledProcessError as e:
        if track:
            track.delete()
        errors['audio_file'] = [f'ffmpeg failed: {e.stderr.decode() if e.stderr else str(e)}']
        return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    except ValueError as e:
        if track:
            track.delete()
        errors['audio_file'] = [str(e)]
        return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        if track:
            track.delete()
        errors['audio_file'] = [f'Processing failed: {str(e)}']
        return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        # Clean up temp files
        for path in [input_path, wav_path, mp3_path]:
            if os.path.exists(path):
                os.remove(path)

    # Success response
    # Return both DB id and public track_id for frontend flows
    data['db_id'] = track.id
    data['track_id'] = track.track_id
    data['title'] = track.title
    data['isrc_code'] = track.isrc_code

    return Response({'message': 'Successful', 'data': data}, status=status.HTTP_201_CREATED)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_tracks_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    artist_id = request.query_params.get('artist_id', "")
    order_by = request.query_params.get('order_by', "")
    page_size = 10

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)


    tracks = Track.objects.filter(artist=artist, is_archived=False).order_by("-created_at")

    if search_query:
        tracks = tracks.filter(
            Q(title__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(isrc_code__icontains=search_query) |
            Q(artist__stage_name__icontains=search_query) |
            Q(artist__stage_name__icontains=search_query) |
            Q(album__title__icontains=search_query) |
            Q(genre__name__icontains=search_query)
        )

    if order_by:
        if order_by == "Genre":
            tracks = tracks.order_by("genre__name")
        if order_by == "Album":
            tracks = tracks.order_by("album__title")
        if order_by == "Title":
            tracks = tracks.order_by("title")
        if order_by == "Release Date":
            tracks = tracks.order_by("release_date")
        if order_by == "Status":
            tracks = tracks.order_by("status")



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
def get_all_tracks_admin_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    order_by = request.query_params.get('order_by', "")
    page_size = 10



    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)


    tracks = Track.objects.all().order_by("-created_at")

    if search_query:
        tracks = tracks.filter(
            Q(title__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(isrc_code__icontains=search_query) |
            Q(artist__stage_name__icontains=search_query) |
            Q(artist__stage_name__icontains=search_query) |
            Q(album__title__icontains=search_query) |
            Q(genre__name__icontains=search_query)
        )

    if order_by:
        if order_by == "Genre":
            tracks = tracks.order_by("genre__name")
        if order_by == "Album":
            tracks = tracks.order_by("album__title")
        if order_by == "Title":
            tracks = tracks.order_by("title")
        if order_by == "Release Date":
            tracks = tracks.order_by("release_date")
        if order_by == "Status":
            tracks = tracks.order_by("status")



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
    data = {}

    track_id = request.query_params.get('track_id')
    period = request.query_params.get('period', 'all-time')

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
    
    playlogs = PlayLog.objects.filter(track=track)
    play_count = playlogs.count()

    ts_qs = playlogs.values('station__name', 'station__region').annotate(plays=Count('id')).order_by('-plays')
   
    _top_station = [{
        "name": s['station__name'],
        "count": s['plays'],
    } for s in ts_qs[:5]]

    plogs = playlogs[:5]
    _playlogs = []

    for log in plogs:
        l = {
          "time": log.played_at, 
                "station": log.station.name, 
                  "region": log.station.region,  
        }
        _playlogs.append(l)



    data['title'] = track.title
    data['artist_name'] = getattr(track.artist, 'stage_name', None)
    data['album_title'] = track.album.title if getattr(track, 'album', None) else None
    data['genre_name'] = track.genre.name if getattr(track, 'genre', None) else None
    # duration can be None for older tracks; render a safe default string
    data['duration'] = get_duration(track.duration) if getattr(track, 'duration', None) else "00:00:00"
    data['release_date'] = track.release_date
    data['plays'] = int(play_count)
    data['cover_art'] = track.cover_art.url if getattr(track.cover_art, 'url', None) else None
    data['audio_file_mp3'] = track.audio_file_mp3.url if track.audio_file_mp3 else None

    data['topStations'] = _top_station
    data['playLogs'] = _playlogs



    # Contributors
    contributors = Contributor.objects.filter(track=track)

    _contributors = []
    for contrib in contributors:
        user = getattr(contrib, 'user', None)
        first = getattr(user, 'first_name', '') if user else ''
        last = getattr(user, 'last_name', '') if user else ''
        username = getattr(user, 'username', '') if user else ''
        email = getattr(user, 'email', '') if user else ''
        display_name = (f"{first} {last}".strip() or username or email)
        con_data = {
            'role': contrib.role,
            'name': display_name,
        }
        _contributors.append(con_data)


    # Plays/Revenue Over Time for this track
    base_qs = playlogs
    if period in ('daily', 'weekly'):
        time_qs = (
            base_qs
            .annotate(day=TruncDate('played_at'))
            .values('day')
            .annotate(revenue=Sum('royalty_amount'), artists=Count('id'), stations=Count('station', distinct=True))
            .order_by('day')
        )
        playsOverTime = [
            {"month": d['day'].strftime('%b %d'), "revenue": float(d['revenue'] or 0), "artists": d['artists'], "stations": d['stations']}
            for d in time_qs
        ]
    elif period in ('monthly', 'all-time'):
        time_qs = (
            base_qs
            .annotate(month=TruncMonth('played_at'))
            .values('month')
            .annotate(revenue=Sum('royalty_amount'), artists=Count('id'), stations=Count('station', distinct=True))
            .order_by('month')
        )
        playsOverTime = [
            {"month": d['month'].strftime('%b %Y'), "revenue": float(d['revenue'] or 0), "artists": d['artists'], "stations": d['stations']}
            for d in time_qs
        ]
    else:
        playsOverTime = []


    radioStations = [
        { "name": "Joy FM", "latitude": 5.5600, "longitude": -0.2100 },
        { "name": "Peace FM", "latitude": 5.5900, "longitude": -0.2400 },
        { "name": "YFM Accra", "latitude": 5.5800, "longitude": -0.2200 },
        { "name": "Luv FM", "latitude": 6.6885, "longitude": -1.6244 },
        { "name": "Skyy Power FM", "latitude": 4.9437, "longitude": -1.7587 },
        { "name": "Cape FM", "latitude": 5.1053, "longitude": -1.2466 },
        { "name": "Radio Central", "latitude": 5.1066, "longitude": -1.2474 },
        { "name": "Radio Savannah", "latitude": 9.4075, "longitude": -0.8419 },
    ];
    data['contributors'] = _contributors
    data['playsOverTime'] = playsOverTime
    data['radioStations'] = radioStations



    payload['message'] = "Successful"
    payload['data'] = data
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


    artist_id = request.data.get('artist_id', None)
    if artist_id:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
            track.artist = artist
        except Artist.DoesNotExist:
            errors['artist'] = ['Artist not found.']

    album_id = request.data.get('album_id', None)
    print("#############")
    print(album_id)
    if album_id:
        try:
            album = Album.objects.get(id=album_id)
            track.album = album
        except Album.DoesNotExist:
            errors['album'] = ['Album not found.']

    genre_id = request.data.get('genre_id', None)
    print("#############")
    print(genre_id)
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




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_upload_track_support_data_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.query_params.get('artist_id', "")

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    # All Genre
    genres = Genre.objects.filter(is_archived=False)
    genres_serializer = GenreSerializer(genres, many=True)
    data['genres'] = genres_serializer.data

    #All Artist Albums

    albums = Album.objects.filter(is_archived=False, artist=artist)
    album_serializer = AlbumSerializer(albums, many=True)
    data['albums'] = album_serializer.data


    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_edit_track_support_data_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.query_params.get('artist_id', "")
    track_id = request.query_params.get('track_id', "")

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    # All Genre
    genres = Genre.objects.filter(is_archived=False)
    genres_serializer = GenreSerializer(genres, many=True)
    data['genres'] = genres_serializer.data

    #All Artist Albums

    albums = Album.objects.filter(is_archived=False, artist=artist)
    album_serializer = AlbumSerializer(albums, many=True)
    data['albums'] = album_serializer.data

    from ..serializers import TrackDetailsSerializer
    track_serializer = TrackDetailsSerializer(track, many=False)
    data['track_details'] = track_serializer.data



    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def upload_track_cover_view(request):
    payload = {}
    data = {}
    errors = {}

    track_id = request.data.get('track_id')
    photo = request.data.get('photo')
 
    if not track_id:
        errors['track_id'] = ['Track ID is required.']
    if not photo:
        errors['photo'] = ['Cover Art is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    track.cover_art=photo
    track.save()

    data['track_id'] = track.id
    data['title'] = track.title

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)

