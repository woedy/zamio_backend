
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist
from music_monitor.models import MatchCache, PlayLog
from publishers.models import PublisherProfile
from publishers.serializers import PublisherPlayLogSerializer, PublisherMatchCacheSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_playlog_for_publisher_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    artist_id = request.query_params.get('artist_id', '')
    log_page_state = request.query_params.get('log_page_state', 'playlogs').lower()
    page_number = request.query_params.get('page', 1)
    page_size = 10

    # Get the current user's publisher profile
    try:
        publisher = PublisherProfile.objects.get(user=request.user)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['Publisher profile not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # If artist_id is provided, validate it belongs to this publisher
    if artist_id:
        try:
            artist = Artist.objects.get(artist_id=artist_id, publisher=publisher)
        except Artist.DoesNotExist:
            errors['artist'] = ['Artist not found or not associated with this publisher.']
    else:
        # If no artist_id provided, get all artists for this publisher
        artist = None

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Prepare querysets - filter by publisher's artists
    if artist:
        # Filter by specific artist
        playlogs_qs = PlayLog.objects.filter(track__artist=artist, is_archived=False).order_by("-created_at")
        match_cache_qs = MatchCache.objects.filter(track__artist=artist).order_by("-matched_at")
    else:
        # Filter by all artists belonging to this publisher
        playlogs_qs = PlayLog.objects.filter(track__artist__publisher=publisher, is_archived=False).order_by("-created_at")
        match_cache_qs = MatchCache.objects.filter(track__artist__publisher=publisher).order_by("-matched_at")

    # Apply search filter
    if search_query:
        playlogs_qs = playlogs_qs.filter(
            Q(track__title__icontains=search_query) |
            Q(track__artist__stage_name__icontains=search_query) |
            Q(track__isrc_code__icontains=search_query) |
            Q(track__album__title__icontains=search_query) |
            Q(track__genre__name__icontains=search_query) |
            Q(station__name__icontains=search_query)
        )
        
        match_cache_qs = match_cache_qs.filter(
            Q(track__title__icontains=search_query) |
            Q(track__artist__stage_name__icontains=search_query) |
            Q(track__isrc_code__icontains=search_query) |
            Q(track__album__title__icontains=search_query) |
            Q(track__genre__name__icontains=search_query) |
            Q(station__name__icontains=search_query)
        )

    # Pagination & Serialization based on active tab
    if log_page_state == 'playlog':
        paginator = Paginator(playlogs_qs, page_size)
        try:
            paginated = paginator.page(page_number)
        except PageNotAnInteger:
            paginated = paginator.page(1)
        except EmptyPage:
            paginated = paginator.page(paginator.num_pages)

        serializer = PublisherPlayLogSerializer(paginated, many=True)
        data['playLogs'] = {
            'results': serializer.data,
            'pagination': {
                'page_number': paginated.number,
                'total_pages': paginator.num_pages,
                'next': paginated.next_page_number() if paginated.has_next() else None,
                'previous': paginated.previous_page_number() if paginated.has_previous() else None,
            }
        }
        data['matchLogs'] = {}

    elif log_page_state == 'matchlog':
        paginator = Paginator(match_cache_qs, page_size)
        try:
            paginated = paginator.page(page_number)
        except PageNotAnInteger:
            paginated = paginator.page(1)
        except EmptyPage:
            paginated = paginator.page(paginator.num_pages)

        serializer = PublisherMatchCacheSerializer(paginated, many=True)
        data['matchLogs'] = {
            'results': serializer.data,
            'pagination': {
                'page_number': paginated.number,
                'total_pages': paginator.num_pages,
                'next': paginated.next_page_number() if paginated.has_next() else None,
                'previous': paginated.previous_page_number() if paginated.has_previous() else None,
            }
        }
        data['playLogs'] = {}

    else:
        payload['message'] = "Invalid log_page_state. Must be 'playlog' or 'matchlog'."
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_publisher_dashboard_stats(request):
    """Get summary statistics for publisher dashboard"""
    payload = {}
    data = {}
    errors = {}

    try:
        publisher = PublisherProfile.objects.get(user=request.user)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['Publisher profile not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Get all artists for this publisher
    publisher_artists = Artist.objects.filter(publisher=publisher)
    
    # Calculate statistics
    total_artists = publisher_artists.count()
    total_tracks = sum(artist.track_set.count() for artist in publisher_artists)
    
    # Get playlogs and match logs for all publisher's artists
    total_playlogs = PlayLog.objects.filter(
        track__artist__publisher=publisher, 
        is_archived=False
    ).count()
    
    total_matchlogs = MatchCache.objects.filter(
        track__artist__publisher=publisher
    ).count()
    
    # Calculate total royalties
    total_royalties = PlayLog.objects.filter(
        track__artist__publisher=publisher,
        is_archived=False
    ).aggregate(
        total=Sum('royalty_amount')
    )['total'] or 0

    data = {
        'total_artists': total_artists,
        'total_tracks': total_tracks,
        'total_playlogs': total_playlogs,
        'total_matchlogs': total_matchlogs,
        'total_royalties': float(total_royalties),
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)
