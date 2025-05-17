
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Artist, Genre

User = get_user_model()



from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_genre(request):
    payload = {}
    data = {}
    errors = {}

    name = request.data.get('name', '')

    if not name:
        errors['name'] = ['Genre name is required.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    genre = Genre.objects.create(name=name, active=True)

    data['genre_id'] = genre.id
    data['name'] = genre.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_201_CREATED)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_genres_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_genres = Genre.objects.filter(is_archived=False)

    if search_query:
        all_genres = all_genres.filter(name__icontains=search_query)

    paginator = Paginator(all_genres, page_size)
    try:
        paginated_genres = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_genres = paginator.page(1)
    except EmptyPage:
        paginated_genres = paginator.page(paginator.num_pages)

    from ..serializers import GenreSerializer  # make sure to create this
    serializer = GenreSerializer(paginated_genres, many=True)

    data['genres'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_genres.number,
        'total_pages': paginator.num_pages,
        'next': paginated_genres.next_page_number() if paginated_genres.has_next() else None,
        'previous': paginated_genres.previous_page_number() if paginated_genres.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_genre_details_view(request):
    payload = {}
    data = {}
    errors = {}

    genre_id = request.query_params.get('genre_id', None)

    if not genre_id:
        errors['genre_id'] = ["Genre ID is required."]

    try:
        genre = Genre.objects.get(id=genre_id)
    except Genre.DoesNotExist:
        errors['genre_id'] = ['Genre does not exist.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import GenreSerializer
    serializer = GenreSerializer(genre, many=False)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_genre(request):
    payload = {}
    data = {}
    errors = {}

    genre_id = request.data.get('genre_id', "")
    name = request.data.get('name', "")

    if not genre_id:
        errors['genre_id'] = ['Genre ID is required.']

    try:
        genre = Genre.objects.get(id=genre_id)
    except Genre.DoesNotExist:
        errors['genre'] = ['Genre not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    if name:
        genre.name = name
    genre.save()

    data['genre_id'] = genre.id
    data['name'] = genre.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_genre(request):
    payload = {}
    errors = {}

    genre_id = request.data.get('genre_id', "")

    if not genre_id:
        errors['genre_id'] = ['Genre ID is required.']

    try:
        genre = Genre.objects.get(id=genre_id)
    except Genre.DoesNotExist:
        errors['genre'] = ['Genre not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    genre.is_archived = True
    genre.save()

    payload['message'] = "Successful"
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_genre(request):
    payload = {}
    errors = {}

    genre_id = request.data.get('genre_id', "")

    if not genre_id:
        errors['genre_id'] = ['Genre ID is required.']

    try:
        genre = Genre.objects.get(id=genre_id)
    except Genre.DoesNotExist:
        errors['genre'] = ['Genre not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    genre.is_archived = False
    genre.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_genre(request):
    payload = {}
    errors = {}

    genre_id = request.data.get('genre_id', "")

    if not genre_id:
        errors['genre_id'] = ['Genre ID is required.']

    try:
        genre = Genre.objects.get(id=genre_id)
    except Genre.DoesNotExist:
        errors['genre'] = ['Genre not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    genre.delete()

    payload['message'] = "Deleted successfully"
    return Response(payload)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_genres_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    genres = Genre.objects.filter(is_archived=True)

    if search_query:
        genres = genres.filter(name__icontains=search_query)

    paginator = Paginator(genres, page_size)
    try:
        paginated_genres = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_genres = paginator.page(1)
    except EmptyPage:
        paginated_genres = paginator.page(paginator.num_pages)

    from ..serializers import GenreSerializer
    serializer = GenreSerializer(paginated_genres, many=True)

    data['genres'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_genres.number,
        'total_pages': paginator.num_pages,
        'next': paginated_genres.next_page_number() if paginated_genres.has_next() else None,
        'previous': paginated_genres.previous_page_number() if paginated_genres.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
