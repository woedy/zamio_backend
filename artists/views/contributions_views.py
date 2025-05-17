
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album, Artist, Contributor, Genre, Track

User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_contributor(request):
    payload = {}
    data = {}
    errors = {}

    name = request.data.get('name', '')
    role = request.data.get('role', '')
    track_id = request.data.get('track_id', '')

    if not name:
        errors['name'] = ['Name is required.']
    if not role:
        errors['role'] = ['Role is required.']
    if not track_id:
        errors['track_id'] = ['Track ID is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    valid_roles = dict(Contributor.ROLE_CHOICES).keys()
    if role and role not in valid_roles:
        errors['role'] = ['Invalid role selected.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    contributor = Contributor.objects.create(
        name=name,
        role=role,
        track=track,
        active=True
    )

    data['contributor_id'] = contributor.id
    data['name'] = contributor.name
    data['role'] = contributor.role
    data['track'] = contributor.track.title

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_contributors_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    contributors = Contributor.objects.filter(is_archived=False)

    if search_query:
        contributors = contributors.filter(
            Q(name__icontains=search_query) |
            Q(role__icontains=search_query) |
            Q(track__title__icontains=search_query)
        )

    paginator = Paginator(contributors, page_size)
    try:
        paginated_contributors = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_contributors = paginator.page(1)
    except EmptyPage:
        paginated_contributors = paginator.page(paginator.num_pages)

    from ..serializers import ContributorSerializer
    serializer = ContributorSerializer(paginated_contributors, many=True)

    data['contributors'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_contributors.number,
        'total_pages': paginator.num_pages,
        'next': paginated_contributors.next_page_number() if paginated_contributors.has_next() else None,
        'previous': paginated_contributors.previous_page_number() if paginated_contributors.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_contributor_details_view(request):
    payload = {}
    errors = {}

    contributor_id = request.query_params.get('contributor_id')

    if not contributor_id:
        errors['contributor_id'] = ['Contributor ID is required.']

    try:
        contributor = Contributor.objects.get(id=contributor_id)
    except Contributor.DoesNotExist:
        errors['contributor'] = ['Contributor not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import ContributorSerializer
    serializer = ContributorSerializer(contributor, many=False)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_contributor(request):
    payload = {}
    data = {}
    errors = {}

    contributor_id = request.data.get('contributor_id')

    if not contributor_id:
        errors['contributor_id'] = ['Contributor ID is required.']

    try:
        contributor = Contributor.objects.get(id=contributor_id)
    except Contributor.DoesNotExist:
        errors['contributor'] = ['Contributor not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    name = request.data.get('name')
    role = request.data.get('role')
    track_id = request.data.get('track_id')

    if name:
        contributor.name = name

    if role:
        valid_roles = dict(Contributor.ROLE_CHOICES).keys()
        if role in valid_roles:
            contributor.role = role
        else:
            errors['role'] = ['Invalid role selected.']

    if track_id:
        try:
            track = Track.objects.get(track_id=track_id)
            contributor.track = track
        except Track.DoesNotExist:
            errors['track'] = ['Track not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    contributor.save()

    data['contributor_id'] = contributor.id
    data['name'] = contributor.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_contributor(request):
    return toggle_contributor_archive_state(request, True)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_contributor(request):
    return toggle_contributor_archive_state(request, False)

def toggle_contributor_archive_state(request, state):
    payload = {}
    errors = {}

    contributor_id = request.data.get('contributor_id', '')

    if not contributor_id:
        errors['contributor_id'] = ['Contributor ID is required.']

    try:
        contributor = Contributor.objects.get(id=contributor_id)
    except Contributor.DoesNotExist:
        errors['contributor'] = ['Contributor not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    contributor.is_archived = state
    contributor.save()

    payload['message'] = "Successful"
    return Response(payload)







@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_contributor(request):
    payload = {}
    errors = {}

    contributor_id = request.data.get('contributor_id', '')

    if not contributor_id:
        errors['contributor_id'] = ['Contributor ID is required.']

    try:
        contributor = Contributor.objects.get(id=contributor_id)
    except Contributor.DoesNotExist:
        errors['contributor'] = ['Contributor not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    contributor.delete()

    payload['message'] = "Contributor deleted successfully."
    return Response(payload)












@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_contributors_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    contributors = Contributor.objects.filter(is_archived=True)

    if search_query:
        contributors = contributors.filter(
            Q(name__icontains=search_query) |
            Q(role__icontains=search_query) |
            Q(track__title__icontains=search_query)
        )

    paginator = Paginator(contributors, page_size)
    try:
        paginated_contributors = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_contributors = paginator.page(1)
    except EmptyPage:
        paginated_contributors = paginator.page(paginator.num_pages)

    from ..serializers import ContributorSerializer
    serializer = ContributorSerializer(paginated_contributors, many=True)

    data['contributors'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_contributors.number,
        'total_pages': paginator.num_pages,
        'next': paginated_contributors.next_page_number() if paginated_contributors.has_next() else None,
        'previous': paginated_contributors.previous_page_number() if paginated_contributors.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
