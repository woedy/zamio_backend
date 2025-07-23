from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from artists.models import Track
from music_monitor.models import MatchCache, PlayLog
from music_monitor.serializers import MatchCacheSerializer, PlayLogSerializer
from stations.models import Station, StationProgram
from rest_framework.authentication import TokenAuthentication

# MatchCache Views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_matchcache(request):
    payload = {}
    errors = {}

    track_id = request.data.get('track_id')
    station_id = request.data.get('station_id')
    station_program_id = request.data.get('station_program_id')

    if not track_id:
        errors['track_id'] = ['Track ID is required.']
    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not station_program_id:
        errors['station_program_id'] = ['Station Program ID is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        track = Track.objects.get(id=track_id)
    except Track.DoesNotExist:
        errors['track_id'] = ['Track does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        station_program = StationProgram.objects.get(id=station_program_id)
    except StationProgram.DoesNotExist:
        errors['station_program_id'] = ['Station Program does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    match_cache = MatchCache.objects.create(
        track=track,
        station=station,
        station_program=station_program
    )

    serializer = MatchCacheSerializer(match_cache)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_matchcache_list(request):
    payload = {}
    data = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_matchcache = MatchCache.objects.all()

    if search_query:
        all_matchcache = all_matchcache.filter(
            Q(track__title__icontains=search_query) |
            Q(station__name__icontains=search_query) |
            Q(station_program__program_name__icontains=search_query)
        )

    paginator = Paginator(all_matchcache, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = MatchCacheSerializer(paginated, many=True)

    data['match_cache'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)




# PlayLog Views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_playlog(request):
    payload = {}
    errors = {}

    track_id = request.data.get('track_id')
    station_id = request.data.get('station_id')
    station_program_id = request.data.get('station_program_id')
    start_time = request.data.get('start_time')
    stop_time = request.data.get('stop_time')
    royalty_amount = request.data.get('royalty_amount')

    if not track_id:
        errors['track_id'] = ['Track ID is required.']
    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not station_program_id:
        errors['station_program_id'] = ['Station Program ID is required.']
    if not start_time:
        errors['start_time'] = ['Start time is required.']
    if not stop_time:
        errors['stop_time'] = ['Stop time is required.']
    if not royalty_amount:
        errors['royalty_amount'] = ['Royalty amount is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        track = Track.objects.get(id=track_id)
    except Track.DoesNotExist:
        errors['track_id'] = ['Track does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        station_program = StationProgram.objects.get(id=station_program_id)
    except StationProgram.DoesNotExist:
        errors['station_program_id'] = ['Station Program does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    playlog = PlayLog.objects.create(
        track=track,
        station=station,
        station_program=station_program,
        start_time=start_time,
        stop_time=stop_time,
        duration=stop_time - start_time,
        royalty_amount=royalty_amount
    )

    serializer = PlayLogSerializer(playlog)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_playlog_list(request):
    payload = {}
    data = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_playlog = PlayLog.objects.all()

    if search_query:
        all_playlog = all_playlog.filter(
            Q(track__title__icontains=search_query) |
            Q(station__name__icontains=search_query) |
            Q(station_program__program_name__icontains=search_query)
        )

    paginator = Paginator(all_playlog, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = PlayLogSerializer(paginated, many=True)

    data['play_logs'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)


from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
@transaction.atomic
def delete_all_matches(request):
    MatchCache.objects.all().delete()
    return HttpResponse("All items deleted successfully.")