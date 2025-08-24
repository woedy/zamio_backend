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

User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_contracts_view(request):
    payload = {}
    data = {}
    errors = {}
    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_artists_contracts = PublishingAgreement.objects.filter(is_archived=False)
    if search_query:
        all_artists_contracts = all_artists_contracts.filter(
            Q(name__icontains=search_query) |
            Q(duration__icontains=search_query) |
            Q(type__icontains=search_query)
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

