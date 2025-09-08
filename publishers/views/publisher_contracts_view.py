from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from publishers.models import PublishingAgreement
from core.utils import get_duration
from music_monitor.models import PlayLog, StreamLog
from publishers.models import PublisherProfile
from artists.models import Artist, Track

User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_contracts_view(request):
    payload = {}
    data = {}
    errors = {}
    search_query = request.query_params.get('search', '').strip()
    page_number = request.query_params.get('page', 1)
    page_size = 10
    publisher_id = request.query_params.get('publisher_id', '').strip()

    # Scope to current publisher
    try:
        if publisher_id:
            publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
        else:
            publisher = PublisherProfile.objects.get(user=request.user)
    except PublisherProfile.DoesNotExist:
        payload['message'] = 'Errors'
        payload['errors'] = {'publisher': ['Publisher profile not found.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    all_artists_contracts = PublishingAgreement.objects.filter(is_archived=False, publisher=publisher).select_related('track', 'songwriter', 'publisher')
    if search_query:
        all_artists_contracts = all_artists_contracts.filter(
            Q(track__title__icontains=search_query)
            | Q(songwriter__stage_name__icontains=search_query)
            | Q(status__icontains=search_query)
        )

    paginator = Paginator(all_artists_contracts, page_size)
    
    try:
        paginated_artists_contracts = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_artists_contracts = paginator.page(1)
    except EmptyPage:
        paginated_artists_contracts = paginator.page(paginator.num_pages)
    
    from ..serializers import PublishingAgreementSerializer
    
    serializer = PublishingAgreementSerializer(paginated_artists_contracts, many=True)
    data['artists_contracts'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_artists_contracts.number,
        'total_pages': paginator.num_pages,
        'count': paginator.count,
        'next': paginated_artists_contracts.next_page_number() if paginated_artists_contracts.has_next() else None,
        'previous': paginated_artists_contracts.previous_page_number() if paginated_artists_contracts.has_previous() else None,
    }
    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_contract_detail_view(request):
    payload = {}
    data = {}
    errors = {}

    contract_id = request.query_params.get('contract_id')

    if not contract_id:
        errors['contract_id'] = ["Contract ID is required"]

    try:
        contract = PublishingAgreement.objects.get(id=contract_id)
    except PublishingAgreement.DoesNotExist:
        errors['contract_id'] = ['Contract does not exist']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import PublishingAgreementSerializer
    serializer = PublishingAgreementSerializer(contract)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def list_tracks_for_artist_view(request):
    payload, data, errors = {}, {}, {}

    artist_id = request.query_params.get('artist_id', '').strip()
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Limit tracks to those belonging to the artist and not archived
    qs = Track.objects.filter(artist=artist, is_archived=False).only('id', 'title')
    data['tracks'] = [{ 'id': t.id, 'title': t.title } for t in qs]

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def create_publishing_agreement_view(request):
    payload, data, errors = {}, {}, {}

    publisher_id = request.data.get('publisher_id', '').strip()
    artist_id = request.data.get('artist_id', '').strip()
    track_id = request.data.get('track_id', '').strip()
    writer_share_raw = request.data.get('writer_share', '').strip()
    publisher_share_raw = request.data.get('publisher_share', '').strip()
    contract_file = request.FILES.get('contract_file')

    # Resolve publisher
    try:
        if publisher_id:
            publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
        else:
            publisher = PublisherProfile.objects.get(user=request.user)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['Publisher profile not found.']

    # Resolve artist
    artist = None
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']
    else:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
        except Artist.DoesNotExist:
            errors['artist_id'] = ['Artist not found.']

    # Resolve track
    track = None
    if not track_id:
        errors['track_id'] = ['Track ID is required.']
    else:
        try:
            track = Track.objects.get(id=track_id, artist=artist)
        except Track.DoesNotExist:
            errors['track_id'] = ['Track not found for the given artist.']

    # Shares
    try:
        w = float(writer_share_raw)
        p = float(publisher_share_raw)
    except Exception:
        errors['shares'] = ['Writer and publisher shares must be numbers.']
        w = p = None

    if w is not None and p is not None:
        if w < 0 or p < 0:
            errors['shares'] = ['Shares must be >= 0.']
        if w > 100 or p > 100:
            errors['shares'] = ['Shares must be <= 100.']
        if abs((w + p) - 100.0) > 1e-6:
            errors['shares'] = ['Writer + Publisher must equal 100%.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Create agreement
    agreement = PublishingAgreement.objects.create(
        publisher=publisher,
        songwriter=artist,
        track=track,
        writer_share=w,
        publisher_share=p,
        contract_file=contract_file if contract_file else None,
        status='pending'
    )

    from ..serializers import PublishingAgreementSerializer
    serializer = PublishingAgreementSerializer(agreement)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_201_CREATED)

