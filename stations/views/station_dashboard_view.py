from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework.authentication import TokenAuthentication

from music_monitor.models import PlayLog
from stations.models import Station
from stations.serializers import AllStationSerializer, StationDetailsSerializer

from rest_framework.permissions import IsAuthenticated


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_dashboard_data(request):
    payload = {}
    data = {}
    errors = {}

    #Data
    totalSongs = 0
    monthly_plays = 0

    topSongs = []
    airplayData = []
    regionalData = []

    station_id = request.query_params.get('station_id')

    if not station_id:
        errors['station_id'] = ["Station ID is required"]

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    




    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

