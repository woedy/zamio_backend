from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from django.contrib.auth import get_user_model
from artists.models import Artist, Track
from bank_account.models import BankAccount
from music_monitor.models import PlayLog


User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def list_artists_royalties_admin_view(request):
    payload, data = {}, {}

    search = request.query_params.get('search', '').strip()
    page_number = request.query_params.get('page', 1)
    page_size = int(request.query_params.get('page_size', 10))

    qs = Artist.objects.select_related('user').all()
    if search:
        qs = qs.filter(Q(stage_name__icontains=search) | Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search))

    paginator = Paginator(qs.order_by('stage_name'), page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    rows = []
    artist_ids = list(page.object_list.values_list('id', flat=True))
    tracks_by_artist = {a.id: list(Track.objects.filter(artist_id=a.id).values_list('id', flat=True)) for a in page.object_list}

    for artist in page.object_list:
        track_ids = tracks_by_artist.get(artist.id, [])
        royalties = PlayLog.objects.filter(track_id__in=track_ids).aggregate(total=Sum('royalty_amount'))['total'] or 0
        plays = PlayLog.objects.filter(track_id__in=track_ids).count()
        try:
            balance = BankAccount.objects.get(user=artist.user).balance
        except BankAccount.DoesNotExist:
            balance = 0

        rows.append({
            'artist_id': artist.artist_id,
            'stage_name': artist.stage_name,
            'name': f"{artist.user.first_name or ''} {artist.user.last_name or ''}".strip(),
            'total_royalties': float(royalties or 0),
            'wallet_balance': float(balance or 0),
            'plays': plays,
        })

    data['artists'] = rows
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
        'count': paginator.count,
        'page_size': page_size,
    }

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

