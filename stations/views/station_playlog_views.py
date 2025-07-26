


from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from stations.models import Station
from music_monitor.models import MatchCache, PlayLog
from stations.serializers import StationMatchCacheSerializer, StationPlayLogSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_station_play_logs(request, station_id):
    logs = PlayLog.objects.filter(station_id=station_id).order_by('-played_at')[:100]
    data = [{
        'track_title': log.track.title,
        'station_name': log.track.station.name,
        'played_at': log.played_at,
        'duration': log.duration.total_seconds() if log.duration else None,
        'source': log.source,
        'royalty_amount': str(log.royalty_amount) if log.royalty_amount else "0.00"
    } for log in logs]
    return Response(data)







@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_station_playlog_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    station_id = request.query_params.get('station_id', '')
    log_page_state = request.query_params.get('log_page_state', 'playlogs').lower()
    page_number = request.query_params.get('page', 1)
    page_size = 10

    # Validate station
    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station'] = ['Station not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Prepare querysets
    playlogs_qs = PlayLog.objects.filter(station=station, is_archived=False).order_by("-created_at")
    match_cache_qs = MatchCache.objects.filter(station=station).order_by("-matched_at")

    #print("####################")
    #print("####################")
    #print("####################")
    #print(match_cache_qs)

    # Apply search filter on playlogs (adjust as needed)
    if search_query:
        playlogs_qs = playlogs_qs.filter(
            Q(track__title__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(track__isrc_code__icontains=search_query) |
            Q(track__station__stage_name__icontains=search_query) |
            Q(track__album__title__icontains=search_query) |
            Q(track__genre__name__icontains=search_query)
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

        serializer = StationPlayLogSerializer(paginated, many=True)
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

        serializer = StationMatchCacheSerializer(paginated, many=True)
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
