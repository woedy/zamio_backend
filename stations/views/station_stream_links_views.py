from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from stations.models import Station, StationStreamLink


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_stream_links_view(request):
    payload = {}
    errors = {}

    station_id = request.query_params.get('station_id', '')
    if not station_id:
        errors['station_id'] = ['Station ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        payload['message'] = 'Errors'
        payload['errors'] = {'station_id': ['Station not found.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    links = StationStreamLink.objects.filter(station=station, is_archived=False).order_by('-created_at')
    data = [
        {
            'id': link.id,
            'link': link.link,
            'active': link.active,
        }
        for link in links
    ]

    return Response({'message': 'Successful', 'data': {'links': data}}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_station_stream_link_view(request):
    payload = {}
    errors = {}

    station_id = request.data.get('station_id', '')
    link = request.data.get('link', '').strip()
    active = request.data.get('active', False)

    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not link:
        errors['link'] = ['Stream link is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        payload['message'] = 'Errors'
        payload['errors'] = {'station_id': ['Station not found.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    link_obj = StationStreamLink.objects.create(station=station, link=link, active=bool(active))

    data = {
        'id': link_obj.id,
        'link': link_obj.link,
        'active': link_obj.active,
    }
    return Response({'message': 'Successful', 'data': data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_station_stream_link_view(request):
    payload = {}
    errors = {}

    link_id = request.data.get('link_id')
    link = request.data.get('link', None)
    active = request.data.get('active', None)

    if not link_id:
        errors['link_id'] = ['Link ID is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        link_obj = StationStreamLink.objects.get(id=link_id, is_archived=False)
    except StationStreamLink.DoesNotExist:
        payload['message'] = 'Errors'
        payload['errors'] = {'link_id': ['Stream link not found.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    if link is not None:
        link_obj.link = link.strip()
    if active is not None:
        link_obj.active = bool(active)
    link_obj.save()

    data = {
        'id': link_obj.id,
        'link': link_obj.link,
        'active': link_obj.active,
    }
    return Response({'message': 'Successful', 'data': data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_station_stream_link_view(request):
    payload = {}
    errors = {}

    link_id = request.data.get('link_id')
    if not link_id:
        errors['link_id'] = ['Link ID is required.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        link_obj = StationStreamLink.objects.get(id=link_id, is_archived=False)
    except StationStreamLink.DoesNotExist:
        payload['message'] = 'Errors'
        payload['errors'] = {'link_id': ['Stream link not found.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    link_obj.is_archived = True
    link_obj.save()

    return Response({'message': 'Successful'}, status=status.HTTP_200_OK)

