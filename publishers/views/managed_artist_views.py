
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist, Contributor, Track
from artists.serializers import AllArtistsSerializer
from bank_account.models import BankAccount
from core.utils import get_duration
from music_monitor.models import PlayLog, StreamLog

User = get_user_model()






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_managed_artist_details_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_artists = Artist.objects.filter(is_archived=False)

    if search_query:
        all_artists = all_artists.filter(
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

    serializer = AllArtistsSerializer(paginated_artists, many=True)

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




