from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from stations.serializers import AllStationProgramSerializer, StationProgramDetailsSerializer

from ..models import Station, User
from rest_framework.permissions import IsAuthenticated

from rest_framework.authentication import TokenAuthentication


from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from ..models import StationProgram, Station
from rest_framework.permissions import IsAuthenticated


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_station_program(request):
    payload = {}
    data = {}
    errors = {}

    program_name = request.data.get('program_name', '')
    description = request.data.get('description', '')
    station_id = request.data.get('station_id', '')

    if not program_name:
        errors['program_name'] = ['Program name is required.']
    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    program = StationProgram.objects.create(
        program_name=program_name,
        description=description,
        station=station,
        active=True
    )

    serializer = StationProgramDetailsSerializer(program)
    data = serializer.data

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_station_programs_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_programs = StationProgram.objects.filter(is_archived=False)

    if search_query:
        all_programs = all_programs.filter(
            Q(program_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    paginator = Paginator(all_programs, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = AllStationProgramSerializer(paginated, many=True)

    data['programs'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_program_details_view(request):
    payload = {}
    errors = {}

    program_id = request.query_params.get('program_id')

    if not program_id:
        errors['program_id'] = ['Program ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        program = StationProgram.objects.get(id=program_id)
    except StationProgram.DoesNotExist:
        errors['program_id'] = ['Program does not exist.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    serializer = StationProgramDetailsSerializer(program)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_station_program(request):
    payload = {}
    errors = {}

    program_id = request.data.get('program_id')
    program_name = request.data.get('program_name', '')
    description = request.data.get('description', '')
    station_id = request.data.get('station_id', '')

    if not program_id:
        errors['program_id'] = ['Program ID is required.']

    try:
        program = StationProgram.objects.get(id=program_id)
    except StationProgram.DoesNotExist:
        errors['program_id'] = ['Program does not exist.']

    if station_id:
        try:
            station = Station.objects.get(station_id=station_id)
            program.station = station
        except Station.DoesNotExist:
            errors['station_id'] = ['Station does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    program.program_name = program_name or program.program_name
    program.description = description or program.description
    program.save()

    serializer = StationProgramDetailsSerializer(program)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data

    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_station_program(request):
    payload = {}
    errors = {}

    program_id = request.data.get('program_id')

    if not program_id:
        errors['program_id'] = ['Program ID is required.']

    try:
        program = StationProgram.objects.get(id=program_id)
    except StationProgram.DoesNotExist:
        errors['program_id'] = ['Program does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    program.is_archived = True
    program.save()

    payload['message'] = 'Successful'
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_station_program(request):
    payload = {}
    errors = {}

    program_id = request.data.get('program_id')

    if not program_id:
        errors['program_id'] = ['Program ID is required.']

    try:
        program = StationProgram.objects.get(id=program_id)
    except StationProgram.DoesNotExist:
        errors['program_id'] = ['Program does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    program.is_archived = False
    program.save()

    payload['message'] = 'Successful'
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_station_program(request):
    payload = {}
    errors = {}

    program_id = request.data.get('program_id')

    if not program_id:
        errors['program_id'] = ['Program ID is required.']

    try:
        program = StationProgram.objects.get(id=program_id)
    except StationProgram.DoesNotExist:
        errors['program_id'] = ['Program does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    program.delete()

    payload['message'] = 'Successful'
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_station_programs_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_programs = StationProgram.objects.filter(is_archived=True)

    if search_query:
        all_programs = all_programs.filter(
            Q(program_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    paginator = Paginator(all_programs, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = AllStationProgramSerializer(paginated, many=True)
    data['programs'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload)
