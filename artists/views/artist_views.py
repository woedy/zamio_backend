
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist

User = get_user_model()



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_artist(request):
    payload = {}
    data = {}
    errors = {}

    user_id = request.data.get('user_id', "")
    name = request.data.get('name', "")
    stage_name = request.data.get('stage_name', "")
    bio = request.data.get('bio', "")
    profile_image = request.data.get('profile_image', "")
    spotify_url = request.data.get('spotify_url', "")
    shazam_url = request.data.get('shazam_url', "")
    instagram = request.data.get('instagram', "")
    twitter = request.data.get('twitter', "")
    website = request.data.get('website', "")
    contact_email = request.data.get('contact_email', "")

    if not name:
        errors['name'] = ['Artist name is required.']

    try:
        user = User.objects.get(user_id=user_id)
    except:
        errors['user_id'] = ['User ID does not exist.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    artist = Artist.objects.create(
        user=user,
        name=name,
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
    data["name"] = artist.name
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
            Q(name__icontains=search_query) |
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
        'name', 'stage_name', 'bio', 'profile_image', 'spotify_url',
        'shazam_url', 'instagram', 'twitter', 'website', 'contact_email', 'active'
    ]
    for field in fields_to_update:
        value = request.data.get(field)
        if value is not None:
            setattr(artist, field, value)

    artist.save()

    data["artist_id"] = artist.id
    data["name"] = artist.name

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
            Q(name__icontains=search_query) |
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


