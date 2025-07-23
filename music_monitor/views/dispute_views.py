from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from artists.models import Track
from core.utils import get_duration
from music_monitor.models import Dispute, MatchCache, PlayLog
from music_monitor.serializers import DisputeSerializer, MatchCacheSerializer, PlayLogSerializer
from stations.models import Station, StationProgram
from rest_framework.authentication import TokenAuthentication



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def flag_match_for_dispute(request):
    payload = {}
    errors = {}

    log_id = request.data.get('playlog_id')
    comment = request.data.get('comment')

    if not log_id:
        errors['playlog_id'] = ['Play log ID is required.']

    if not comment:
        errors['comment'] = ['Comment is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        playlog = PlayLog.objects.get(id=log_id)
    except PlayLog.DoesNotExist:
        errors['playlog_id'] = ['Playlog does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)


    dispute = Dispute.objects.create(
        playlog=playlog,
        dispute_status="Flagged",
        dispute_comments=comment
    )

    playlog.flagged = True
    playlog.save()

    serializer = DisputeSerializer(dispute)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_201_CREATED)







@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_station_disputes_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    station_id = request.query_params.get('station_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station'] = ['Station not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch Dispute
    disputes_qs = Dispute.objects.filter(
        playlog__station=station,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        disputes_qs = disputes_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        disputes_qs = disputes_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        disputes_qs = disputes_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(disputes_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_disputes = []
    for dispute in page.object_list:
        formatted_disputes.append({
            "id": dispute.id,
            "comment": dispute.dispute_comments,
            "status": dispute.dispute_status,
            "track_title": dispute.playlog.track.title,
            "artist_name": dispute.playlog.track.artist.stage_name,
            "duration": get_duration(dispute.playlog.duration),
            "start_time": dispute.playlog.start_time.strftime('%Y-%m-%d ~ %H:%M:%S'),
            "stop_time": dispute.playlog.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S'),
            "confidence": dispute.playlog.avg_confidence_score,
            "earnings": dispute.playlog.royalty_amount,
            "timestamp": timesince(dispute.created_at) + " ago" if dispute.created_at else "Just now"
        })

    data['disputes'] = formatted_disputes
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_match_dispute_details_view(request):
    payload = {}
    errors = {}
    data = {}

    dispute_id = request.query_params.get('dispute_id')

    if not dispute_id:
        errors['dispute_id'] = ['Dispute ID is required.']

    try:
        dispute = Dispute.objects.get(id=dispute_id)
    except Dispute.DoesNotExist:
        errors['dispute_id'] = ['Dispute not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)



    data['id'] = dispute.id
    data['track_title'] = dispute.playlog.track.title
    data['artist_name'] = dispute.playlog.track.artist.stage_name
    data['duration'] = get_duration(dispute.playlog.track.duration)
    data['cover_art'] = dispute.playlog.track.cover_art.url
    data['audio_file_mp3'] = dispute.playlog.track.audio_file_mp3.url if dispute.playlog.track.audio_file_mp3 else None




    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)







@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def review_match_for_dispute(request):
    payload = {}
    errors = {}

    dispute_id = request.data.get('dispute_id')
    comment = request.data.get('comment')

    if not dispute_id:
        errors['dispute_id'] = ['Dispute ID is required.']

    if not comment:
        errors['comment'] = ['Comment is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        dispute = Dispute.objects.get(id=dispute_id)
    except Dispute.DoesNotExist:
        errors['dispute_id'] = ['Dispute does not exist.']
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)
    

    #dispute.dispute_status = ""

    serializer = DisputeSerializer(dispute)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)












from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
@transaction.atomic
def delete_all_matches(request):
    MatchCache.objects.all().delete()
    return HttpResponse("All items deleted successfully.")