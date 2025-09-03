
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email
from artists.models import Album, Artist, Contributor, Genre, Track
from bank_account.models import BankAccount
from publishers.models import PublisherProfile
import secrets

User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_contributor(request):
    payload = {}
    data = {}
    errors = {}

    email = request.data.get('email', '').strip()
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()
    role = request.data.get('role', '').strip()
    percent_split = request.data.get('percent_split', '').strip()
    track_id = request.data.get('track_id', '').strip()
    publisher_id = request.data.get('publisher_id', '').strip()
    artist_self = str(request.data.get('artist_self', '')).lower() in ['1', 'true', 'yes']

    
    if not artist_self:
        if not email:
            errors['email'] = ['User email is required.']
        elif not is_valid_email(email):
            errors['email'] = ['Valid email required.']

    if not role:
        errors['role'] = ['Role is required.']
    if not track_id:
        errors['track_id'] = ['Track ID is required.']
    if not percent_split:
        errors['percent_split'] = ['Percent Split is required.']

    try:
        track = Track.objects.get(track_id=track_id)
    except Track.DoesNotExist:
        errors['track'] = ['Track not found.']

    publisher = None
    if publisher_id:
        try:
            publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
        except PublisherProfile.DoesNotExist:
            errors['publisher_id'] = ['Publisher not found.']

    valid_roles = dict(Contributor.ROLE_CHOICES).keys()
    if not role:
        # default a sensible role when not provided
        role = 'Composer' if 'Composer' in valid_roles else list(valid_roles)[0]
    if role and role not in valid_roles:
        errors['role'] = ['Invalid role selected.']

    # percent_split validation
    try:
        ps_val = Decimal(percent_split)
    except Exception:
        errors['percent_split'] = ['Percent split must be a number.']
    else:
        if ps_val < 0 or ps_val > 100:
            errors['percent_split'] = ['Percent split must be between 0 and 100.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    # Resolve user for contributor
    if artist_self:
        user = track.artist.user
    else:
        user = User.objects.filter(email=email).first()
        if not user:
            # Minimal user; a later invite flow can set password
            user = User.objects.create(
                email=email,
                first_name=first_name or None,
                last_name=last_name or None,
            )
            # Optionally set user_type
            user.user_type = 'contributor'
            # Set a random password (not used until activation)
            user.set_password(secrets.token_urlsafe(12))
            user.save()

    # Avoid duplicate contributor for same user-track
    if Contributor.objects.filter(track=track, user=user, is_archived=False).exists():
        payload['message'] = 'Errors'
        payload['errors'] = {'contributor': ['Contributor already added to this track.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    contributor = Contributor.objects.create(
        user=user,
        role=role,
        track=track,
        publisher=publisher,
        percent_split=ps_val,
        active=True
    )
    
    BankAccount.objects.get_or_create(
        user=user,
        defaults={
            'balance': Decimal('0.00'),
            'currency': 'Ghc',
        }
    )



    display_name = (f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or user.email)
    data['contributor_id'] = contributor.id
    data['name'] = display_name
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
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(role__icontains=search_query) |
            Q(track__title__icontains=search_query)
        )


    if filter:
        if filter == "Name":
            contributors = contributors.order_by("name")
        if filter == "Role":
            contributors = contributors.order_by("role")
        if filter == "Split":
            contributors = contributors.order_by("percent_split")


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

    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')
    role = request.data.get('role')
    track_id = request.data.get('track_id')
    percent_split = request.data.get('percent_split')

    if first_name is not None or last_name is not None:
        if first_name is not None:
            contributor.user.first_name = first_name
        if last_name is not None:
            contributor.user.last_name = last_name
        contributor.user.save()

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

    if percent_split is not None:
        try:
            ps_val = Decimal(percent_split)
            if ps_val < 0 or ps_val > 100:
                errors['percent_split'] = ['Percent split must be between 0 and 100.']
            else:
                contributor.percent_split = ps_val
        except Exception:
            errors['percent_split'] = ['Percent split must be a number.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    contributor.save()

    data['contributor_id'] = contributor.id
    data['name'] = (f"{contributor.user.first_name or ''} {contributor.user.last_name or ''}".strip() or contributor.user.username or contributor.user.email)

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
def get_artist_contributor_choices_view(request):
    """Return distinct existing contributor users for an artist to pick from."""
    payload, data, errors = {}, {}, {}

    artist_id = request.query_params.get('artist_id', '').strip()
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Distinct contributor users across this artist's tracks
    qs = (
        Contributor.objects
        .filter(track__artist=artist, is_archived=False)
        .select_related('user')
        .values('user_id', 'user__first_name', 'user__last_name', 'user__email')
        .order_by('user_id')
    )

    seen = set()
    choices = []
    for row in qs:
        uid = row['user_id']
        if uid in seen:
            continue
        seen.add(uid)
        choices.append({
            'user_id': uid,
            'first_name': row['user__first_name'] or '',
            'last_name': row['user__last_name'] or '',
            'email': row['user__email'] or '',
        })

    data['contributors'] = choices
    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)












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
