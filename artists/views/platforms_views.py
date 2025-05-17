
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album, Artist, Genre, PlatformAvailability, Track

User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_platform_availability(request):
    payload = {}
    data = {}
    errors = {}

    track_id = request.data.get('track_id', '')
    platform = request.data.get('platform', '')
    url = request.data.get('url', '')

    if not track_id:
        errors['track_id'] = ['Track ID is required.']
    if not platform:
        errors['platform'] = ['Platform is required.']
    if not url:
        errors['url'] = ['Platform URL is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    valid_platforms = dict(PlatformAvailability.PLATFORM_CHOICES).keys()
    if platform and platform not in valid_platforms:
        errors['platform'] = ['Invalid platform selected.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    availability = PlatformAvailability.objects.create(
        track=track,
        platform=platform,
        url=url,
        active=True
    )

    data['id'] = availability.id
    data['track'] = availability.track.title
    data['platform'] = availability.platform
    data['url'] = availability.url

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)










@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_platform_availability_view(request):
    payload = {}
    data = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    availabilities = PlatformAvailability.objects.filter(is_archived=False)

    if search_query:
        availabilities = availabilities.filter(
            Q(platform__icontains=search_query) |
            Q(track__title__icontains=search_query)
        )

    paginator = Paginator(availabilities, page_size)
    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    from ..serializers import PlatformAvailabilitySerializer
    serializer = PlatformAvailabilitySerializer(paginated, many=True)

    data['availabilities'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_platform_availability_details_view(request):
    payload = {}
    errors = {}

    availability_id = request.query_params.get('id')

    if not availability_id:
        errors['id'] = ['ID is required.']

    try:
        availability = PlatformAvailability.objects.get(id=availability_id)
    except PlatformAvailability.DoesNotExist:
        errors['id'] = ['Availability record not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import PlatformAvailabilitySerializer
    serializer = PlatformAvailabilitySerializer(availability)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_platform_availability(request):
    payload = {}
    data = {}
    errors = {}

    availability_id = request.data.get('id')

    if not availability_id:
        errors['id'] = ['ID is required.']

    try:
        availability = PlatformAvailability.objects.get(id=availability_id)
    except PlatformAvailability.DoesNotExist:
        errors['id'] = ['Availability not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    platform = request.data.get('platform')
    url = request.data.get('url')
    track_id = request.data.get('track_id')

    if platform:
        valid_platforms = dict(PlatformAvailability.PLATFORM_CHOICES).keys()
        if platform in valid_platforms:
            availability.platform = platform
        else:
            errors['platform'] = ['Invalid platform selected.']

    if url:
        availability.url = url

    if track_id:
        try:
            track = Track.objects.get(id=track_id)
            availability.track = track
        except Track.DoesNotExist:
            errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    availability.save()

    data['id'] = availability.id
    data['platform'] = availability.platform
    data['track'] = availability.track.title

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_platform_availability(request):
    return toggle_availability_archive_state(request, True)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_platform_availability(request):
    return toggle_availability_archive_state(request, False)

def toggle_availability_archive_state(request, state):
    payload = {}
    errors = {}

    availability_id = request.data.get('id', '')

    if not availability_id:
        errors['id'] = ['ID is required.']

    try:
        availability = PlatformAvailability.objects.get(id=availability_id)
    except PlatformAvailability.DoesNotExist:
        errors['id'] = ['Availability not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    availability.is_archived = state
    availability.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_platform_availability(request):
    payload = {}
    errors = {}

    availability_id = request.data.get('id', '')

    if not availability_id:
        errors['id'] = ['ID is required.']

    try:
        availability = PlatformAvailability.objects.get(id=availability_id)
    except PlatformAvailability.DoesNotExist:
        errors['id'] = ['Availability not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    availability.delete()

    payload['message'] = "Platform availability deleted successfully."
    return Response(payload)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_platform_availability_view(request):
    payload = {}
    data = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    archived = PlatformAvailability.objects.filter(is_archived=True)

    if search_query:
        archived = archived.filter(
            Q(platform__icontains=search_query) |
            Q(track__title__icontains=search_query)
        )

    paginator = Paginator(archived, page_size)
    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    from ..serializers import PlatformAvailabilitySerializer
    serializer = PlatformAvailabilitySerializer(paginated, many=True)

    data['availabilities'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
