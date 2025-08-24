
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album, Artist

User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_album(request):
    payload = {}
    data = {}
    errors = {}

    title = request.data.get('title', "")
    artist_id = request.data.get('artist_id', "")
    release_date = request.data.get('release_date', "").strip()

    if not title:
        errors['title'] = ['Album title is required.']
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

    album = Album.objects.create(
        title=title,
        artist=artist,
        release_date=release_date or None,
        active=True
    )

    data['album_id'] = album.id
    data['title'] = album.title
    data['upc_code'] = album.upc_code

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_albums_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    albums = Album.objects.filter(is_archived=False)

    if search_query:
        albums = albums.filter(
            Q(title__icontains=search_query) |
            Q(upc_code__icontains=search_query) |
            Q(artist__name__icontains=search_query) |
            Q(artist__stage_name__icontains=search_query)
        )

    paginator = Paginator(albums, page_size)
    try:
        paginated_albums = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_albums = paginator.page(1)
    except EmptyPage:
        paginated_albums = paginator.page(paginator.num_pages)

    from ..serializers import AlbumSerializer
    serializer = AlbumSerializer(paginated_albums, many=True)

    data['albums'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_albums.number,
        'total_pages': paginator.num_pages,
        'next': paginated_albums.next_page_number() if paginated_albums.has_next() else None,
        'previous': paginated_albums.previous_page_number() if paginated_albums.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)









@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_album_details_view(request):
    payload = {}
    data = {}
    errors = {}

    album_id = request.query_params.get('album_id', None)

    if not album_id:
        errors['album_id'] = ["Album ID is required."]

    try:
        album = Album.objects.get(id=album_id)
    except Album.DoesNotExist:
        errors['album_id'] = ['Album not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import AlbumSerializer
    serializer = AlbumSerializer(album, many=False)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_album(request):
    payload = {}
    data = {}
    errors = {}

    album_id = request.data.get('album_id', "")
    title = request.data.get('title', "")
    artist_id = request.data.get('artist_id', "")
    release_date = request.data.get('release_date', "")
    upc_code = request.data.get('upc_code', "")
    cover_art = request.FILES.get('cover_art', None)

    if not album_id:
        errors['album_id'] = ['Album ID is required.']

    try:
        album = Album.objects.get(id=album_id)
    except Album.DoesNotExist:
        errors['album'] = ['Album not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    if title:
        album.title = title
    if release_date:
        album.release_date = release_date
    if cover_art:
        album.cover_art = cover_art
    if upc_code and upc_code != album.upc_code:
        if Album.objects.filter(upc_code=upc_code).exists():
            errors['upc_code'] = ['UPC already exists.']
        else:
            album.upc_code = upc_code
    if artist_id:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
            album.artist = artist
        except Artist.DoesNotExist:
            errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    album.save()

    data['album_id'] = album.id
    data['title'] = album.title
    data['upc_code'] = album.upc_code

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_album(request):
    payload = {}
    errors = {}

    album_id = request.data.get('album_id', "")

    if not album_id:
        errors['album_id'] = ['Album ID is required.']

    try:
        album = Album.objects.get(id=album_id)
    except Album.DoesNotExist:
        errors['album'] = ['Album not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    album.is_archived = True
    album.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_album(request):
    payload = {}
    errors = {}

    album_id = request.data.get('album_id', "")

    if not album_id:
        errors['album_id'] = ['Album ID is required.']

    try:
        album = Album.objects.get(id=album_id)
    except Album.DoesNotExist:
        errors['album'] = ['Album not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    album.is_archived = False
    album.save()

    payload['message'] = "Successful"
    return Response(payload)



def delete_album(request):
    payload = {}
    errors = {}

    album_id = request.data.get('album_id', "")

    if not album_id:
        errors['album_id'] = ['Album ID is required.']

    try:
        album = Album.objects.get(id=album_id)
    except Album.DoesNotExist:
        errors['album'] = ['Album not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    album.delete()

    payload['message'] = "Deleted successfully"
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_albums_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    albums = Album.objects.filter(is_archived=True)

    if search_query:
        albums = albums.filter(
            Q(title__icontains=search_query) |
            Q(upc_code__icontains=search_query) |
            Q(artist__name__icontains=search_query)
        )

    paginator = Paginator(albums, page_size)
    try:
        paginated_albums = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_albums = paginator.page(1)
    except EmptyPage:
        paginated_albums = paginator.page(paginator.num_pages)

    from ..serializers import AlbumSerializer
    serializer = AlbumSerializer(paginated_albums, many=True)

    data['albums'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_albums.number,
        'total_pages': paginator.num_pages,
        'next': paginated_albums.next_page_number() if paginated_albums.has_next() else None,
        'previous': paginated_albums.previous_page_number() if paginated_albums.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
