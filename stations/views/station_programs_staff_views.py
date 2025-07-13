from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from ..models import ProgramStaff, StationProgram
from ..serializers import ProgramStaffSerializer, ProgramStaffDetailsSerializer
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_program_staff(request):
    payload = {}
    data = {}
    errors = {}

    name = request.data.get('name', '')
    role = request.data.get('role', '')
    station_program_id = request.data.get('program_id', '')

    if not name:
        errors['name'] = ['Name is required.']
    if not role:
        errors['role'] = ['Role is required.']
    if not station_program_id:
        errors['station_program_id'] = ['Station Program ID is required.']

    try:
        station_program = StationProgram.objects.get(id=station_program_id)
    except StationProgram.DoesNotExist:
        errors['station_program_id'] = ['Station program does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff = ProgramStaff.objects.create(
        name=name,
        role=role,
        station_program=station_program,
        active=True
    )

    serializer = ProgramStaffDetailsSerializer(staff)
    data = serializer.data

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_program_staff_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    staff_qs = ProgramStaff.objects.filter(is_archived=False)

    if search_query:
        staff_qs = staff_qs.filter(
            Q(name__icontains=search_query) |
            Q(role__icontains=search_query)
        )

    paginator = Paginator(staff_qs, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = ProgramStaffSerializer(paginated, many=True)
    data['program_staff'] = serializer.data
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
def get_program_staff_details_view(request):
    payload = {}
    errors = {}

    staff_id = request.query_params.get('staff_id')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        staff = ProgramStaff.objects.get(id=staff_id)
    except ProgramStaff.DoesNotExist:
        errors['staff_id'] = ['Program staff does not exist.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    serializer = ProgramStaffDetailsSerializer(staff)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_program_staff(request):
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id', '')
    name = request.data.get('name', '')
    role = request.data.get('role', '')
    station_program_id = request.data.get('station_program_id', '')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = ProgramStaff.objects.get(id=staff_id)
    except ProgramStaff.DoesNotExist:
        errors['staff_id'] = ['Program staff does not exist.']

    if station_program_id:
        try:
            station_program = StationProgram.objects.get(id=station_program_id)
            staff.station_program = station_program
        except StationProgram.DoesNotExist:
            errors['station_program_id'] = ['Station program does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff.name = name or staff.name
    staff.role = role or staff.role
    staff.save()

    serializer = ProgramStaffDetailsSerializer(staff)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data

    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_program_staff(request):
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id', '')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = ProgramStaff.objects.get(id=staff_id)
    except ProgramStaff.DoesNotExist:
        errors['staff_id'] = ['Program staff does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff.is_archived = True
    staff.save()

    payload['message'] = 'Successful'
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_program_staff(request):
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id', '')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = ProgramStaff.objects.get(id=staff_id)
    except ProgramStaff.DoesNotExist:
        errors['staff_id'] = ['Program staff does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff.is_archived = False
    staff.save()

    payload['message'] = 'Successful'
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_program_staff(request):
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id', '')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = ProgramStaff.objects.get(id=staff_id)
    except ProgramStaff.DoesNotExist:
        errors['staff_id'] = ['Program staff does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff.delete()

    payload['message'] = 'Successful'
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_program_staff_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    staff_qs = ProgramStaff.objects.filter(is_archived=True)

    if search_query:
        staff_qs = staff_qs.filter(
            Q(name__icontains=search_query) |
            Q(role__icontains=search_query)
        )

    paginator = Paginator(staff_qs, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = ProgramStaffSerializer(paginated, many=True)
    data['program_staff'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload)
