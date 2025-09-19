from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from ..models import Station, StationStaff
from ..serializers import StationStaffSerializer, StationStaffDetailsSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_station_staff(request):
    """Add a new staff member to a station"""
    payload = {}
    errors = {}

    station_id = request.data.get('station_id', '')
    name = request.data.get('name', '')
    email = request.data.get('email', '')
    phone = request.data.get('phone', '')
    role = request.data.get('role', 'presenter')
    permission_level = request.data.get('permission_level', 'view')
    emergency_contact = request.data.get('emergency_contact', '')
    emergency_phone = request.data.get('emergency_phone', '')
    hire_date = request.data.get('hire_date', None)
    employee_id = request.data.get('employee_id', '')
    department = request.data.get('department', '')
    can_upload_playlogs = request.data.get('can_upload_playlogs', False)
    can_manage_streams = request.data.get('can_manage_streams', False)
    can_view_analytics = request.data.get('can_view_analytics', True)

    # Validation
    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not name:
        errors['name'] = ['Name is required.']
    if not email:
        errors['email'] = ['Email is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']

    # Check for duplicate email within station
    if email and station_id:
        existing_staff = StationStaff.objects.filter(
            station__station_id=station_id, 
            email=email, 
            is_archived=False
        ).exists()
        if existing_staff:
            errors['email'] = ['Staff member with this email already exists for this station.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff = StationStaff.objects.create(
        station=station,
        name=name,
        email=email,
        phone=phone,
        role=role,
        permission_level=permission_level,
        emergency_contact=emergency_contact,
        emergency_phone=emergency_phone,
        hire_date=hire_date,
        employee_id=employee_id,
        department=department,
        can_upload_playlogs=can_upload_playlogs,
        can_manage_streams=can_manage_streams,
        can_view_analytics=can_view_analytics,
        active=True
    )

    serializer = StationStaffDetailsSerializer(staff)
    payload['message'] = 'Staff member added successfully'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_staff_list(request):
    """Get paginated list of station staff"""
    payload = {}
    data = {}
    errors = {}

    station_id = request.query_params.get('station_id', '')
    search_query = request.query_params.get('search', '')
    role_filter = request.query_params.get('role', '')
    page_number = request.query_params.get('page', 1)
    page_size = int(request.query_params.get('page_size', 10))

    if not station_id:
        errors['station_id'] = ['Station ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff_qs = StationStaff.objects.filter(station=station, is_archived=False)

    # Apply filters
    if search_query:
        staff_qs = staff_qs.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(role__icontains=search_query) |
            Q(department__icontains=search_query) |
            Q(employee_id__icontains=search_query)
        )

    if role_filter:
        staff_qs = staff_qs.filter(role=role_filter)

    staff_qs = staff_qs.order_by('-created_at')

    paginator = Paginator(staff_qs, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = StationStaffSerializer(paginated, many=True)
    data['staff'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    # Add role choices for frontend
    data['role_choices'] = StationStaff.STAFF_ROLES
    data['permission_choices'] = StationStaff.PERMISSION_LEVELS

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_staff_details(request):
    """Get details of a specific staff member"""
    payload = {}
    errors = {}

    staff_id = request.query_params.get('staff_id')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        staff = StationStaff.objects.get(id=staff_id, is_archived=False)
    except StationStaff.DoesNotExist:
        errors['staff_id'] = ['Staff member does not exist.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    serializer = StationStaffDetailsSerializer(staff)
    payload['message'] = 'Successful'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_station_staff(request):
    """Edit station staff member details"""
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id', '')
    name = request.data.get('name', '')
    email = request.data.get('email', '')
    phone = request.data.get('phone', '')
    role = request.data.get('role', '')
    permission_level = request.data.get('permission_level', '')
    emergency_contact = request.data.get('emergency_contact', '')
    emergency_phone = request.data.get('emergency_phone', '')
    hire_date = request.data.get('hire_date', None)
    employee_id = request.data.get('employee_id', '')
    department = request.data.get('department', '')
    can_upload_playlogs = request.data.get('can_upload_playlogs')
    can_manage_streams = request.data.get('can_manage_streams')
    can_view_analytics = request.data.get('can_view_analytics')
    active = request.data.get('active')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = StationStaff.objects.get(id=staff_id, is_archived=False)
    except StationStaff.DoesNotExist:
        errors['staff_id'] = ['Staff member does not exist.']

    # Check for duplicate email within station (excluding current staff)
    if email and staff:
        existing_staff = StationStaff.objects.filter(
            station=staff.station, 
            email=email, 
            is_archived=False
        ).exclude(id=staff_id).exists()
        if existing_staff:
            errors['email'] = ['Another staff member with this email already exists for this station.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Update fields
    if name:
        staff.name = name
    if email:
        staff.email = email
    if phone is not None:
        staff.phone = phone
    if role:
        staff.role = role
    if permission_level:
        staff.permission_level = permission_level
    if emergency_contact is not None:
        staff.emergency_contact = emergency_contact
    if emergency_phone is not None:
        staff.emergency_phone = emergency_phone
    if hire_date is not None:
        staff.hire_date = hire_date
    if employee_id is not None:
        staff.employee_id = employee_id
    if department is not None:
        staff.department = department
    if can_upload_playlogs is not None:
        staff.can_upload_playlogs = can_upload_playlogs
    if can_manage_streams is not None:
        staff.can_manage_streams = can_manage_streams
    if can_view_analytics is not None:
        staff.can_view_analytics = can_view_analytics
    if active is not None:
        staff.active = active

    staff.save()

    serializer = StationStaffDetailsSerializer(staff)
    payload['message'] = 'Staff member updated successfully'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_station_staff(request):
    """Archive (soft delete) a staff member"""
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id')

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = StationStaff.objects.get(id=staff_id)
    except StationStaff.DoesNotExist:
        errors['staff_id'] = ['Staff member does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff.is_archived = True
    staff.active = False
    staff.save()

    payload['message'] = 'Staff member archived successfully'
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def activate_station_staff(request):
    """Activate/deactivate a staff member"""
    payload = {}
    errors = {}

    staff_id = request.data.get('staff_id')
    active = request.data.get('active', True)

    if not staff_id:
        errors['staff_id'] = ['Staff ID is required.']

    try:
        staff = StationStaff.objects.get(id=staff_id, is_archived=False)
    except StationStaff.DoesNotExist:
        errors['staff_id'] = ['Staff member does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    staff.active = active
    staff.save()

    action = 'activated' if active else 'deactivated'
    payload['message'] = f'Staff member {action} successfully'
    return Response(payload, status=status.HTTP_200_OK)