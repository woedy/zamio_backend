
import os
import subprocess
import uuid
import shutil

from click import File
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
import librosa
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album, Artist, Contributor, Fingerprint, Genre, Track
from artists.serializers import AlbumSerializer, GenreSerializer
from django.core.files.base import ContentFile

from artists.utils.fingerprint_tracks import simple_fingerprint
from datetime import timedelta

from bank_account.models import BankAccount, Transaction
from music_monitor.models import PlayLog


User = get_user_model()



from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from decimal import Decimal
from datetime import datetime



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_artist_payment_view(request):
    payload = {}
    errors = {}
    data = {}

    artist_id = request.query_params.get('artist_id')

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Get bank balance
    try:
        artist_account = BankAccount.objects.get(user=artist.user)
        total_balance = artist_account.balance
    except BankAccount.DoesNotExist:
        artist_account = None
        total_balance = Decimal('0.00')

    artist_tracks = Track.objects.filter(artist=artist)

    # DEBUGGING - check tracks
    print(f"Tracks found for artist {artist.artist_id}: {artist_tracks.count()}")

    # RADIO (PlayLogs)
    radio_total = PlayLog.objects.filter(track__in=artist_tracks, 
                                         #claimed=True
                                         ).aggregate(
        total=Sum('royalty_amount')
    )['total'] or Decimal('0.00')

    print("Radio Royalty Total:", radio_total)

    # Streaming removed from scope; keep as zero for compatibility
    streaming_total = Decimal('0.00')

    # DISTRO: fallback — total minus other sources
    all_royalties = artist_tracks.aggregate(total=Sum('royalty_amount'))['total'] or Decimal('0.00')
    distro_total = all_royalties - radio_total - streaming_total
    if distro_total < 0:
        distro_total = Decimal('0.00')

    # TRANSACTIONS
    transactions = Transaction.objects.none()
    if artist_account:
        transactions = Transaction.objects.filter(
            bank_account=artist_account,
            #status='Paid'
        ).order_by('-timestamp')[:5]

    print("Transaction count:", transactions.count())

    history = [
        {
            "date": tx.timestamp.strftime('%Y-%m-%d'),
            "amount": float(tx.amount),
            "method": tx.payment_method,
            "status": tx.status
        } for tx in transactions
    ]

    wallet = {
        "total": float(total_balance),
        "sources": {
            "radio": float(radio_total),
            "distro": float(distro_total),
        },
        "royaltyRates": {
            "radio": "GHS 1.20 per spin",
        },
        "history": history,
    }

    # Royalty Breakdown (monthly revenue and plays for recent months)
    monthly_qs = (
        PlayLog.objects
        .filter(track__in=artist_tracks)
        .annotate(month=TruncMonth('played_at'))
        .values('month')
        .annotate(revenue=Sum('royalty_amount'), plays=Count('id'), stations=Count('station', distinct=True))
        .order_by('-month')[:7]
    )

    # Reverse to chronological order and format month as short name
    breakdown = []
    for row in reversed(list(monthly_qs)):
        m = row['month']
        breakdown.append({
            "month": m.strftime('%b') if hasattr(m, 'strftime') else str(m),
            "revenue": float(row['revenue'] or 0),
            "plays": int(row['plays'] or 0),
            "stations": int(row['stations'] or 0),
        })

    wallet["royaltyBreakdown"] = breakdown

    data['wallet'] = wallet
    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
