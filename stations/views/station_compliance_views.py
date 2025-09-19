from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from ..models import Station
from ..serializers import StationComplianceSerializer, StationDetailsSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def update_station_compliance(request):
    """Update station compliance information"""
    payload = {}
    errors = {}

    station_id = request.data.get('station_id', '')
    regulatory_body = request.data.get('regulatory_body', '')
    compliance_contact_name = request.data.get('compliance_contact_name', '')
    compliance_contact_email = request.data.get('compliance_contact_email', '')
    compliance_contact_phone = request.data.get('compliance_contact_phone', '')
    license_number = request.data.get('license_number', '')
    operating_hours_start = request.data.get('operating_hours_start', '')
    operating_hours_end = request.data.get('operating_hours_end', '')
    timezone_val = request.data.get('timezone', 'Africa/Accra')
    website_url = request.data.get('website_url', '')
    social_media_links = request.data.get('social_media_links', {})
    broadcast_frequency = request.data.get('broadcast_frequency', '')
    transmission_power = request.data.get('transmission_power', '')

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

    # Update compliance fields
    if regulatory_body:
        station.regulatory_body = regulatory_body
    if compliance_contact_name:
        station.compliance_contact_name = compliance_contact_name
    if compliance_contact_email:
        station.compliance_contact_email = compliance_contact_email
    if compliance_contact_phone:
        station.compliance_contact_phone = compliance_contact_phone
    if license_number:
        station.license_number = license_number
    if operating_hours_start:
        station.operating_hours_start = operating_hours_start
    if operating_hours_end:
        station.operating_hours_end = operating_hours_end
    if timezone_val:
        station.timezone = timezone_val
    if website_url:
        station.website_url = website_url
    if social_media_links:
        station.social_media_links = social_media_links
    if broadcast_frequency:
        station.broadcast_frequency = broadcast_frequency
    if transmission_power:
        station.transmission_power = transmission_power

    station.save()

    serializer = StationDetailsSerializer(station)
    payload['message'] = 'Station compliance information updated successfully'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_stations_for_verification(request):
    """Get stations pending verification (admin only)"""
    payload = {}
    data = {}

    # Check if user is admin (you may need to adjust this based on your user model)
    if not request.user.is_staff:
        payload['message'] = 'Permission denied. Admin access required.'
        return Response(payload, status=status.HTTP_403_FORBIDDEN)

    search_query = request.query_params.get('search', '')
    verification_status = request.query_params.get('status', 'pending')
    page_number = request.query_params.get('page', 1)
    page_size = int(request.query_params.get('page_size', 10))

    stations_qs = Station.objects.filter(is_archived=False)

    # Filter by verification status
    if verification_status:
        stations_qs = stations_qs.filter(verification_status=verification_status)

    # Apply search filter
    if search_query:
        stations_qs = stations_qs.filter(
            Q(name__icontains=search_query) |
            Q(license_number__icontains=search_query) |
            Q(regulatory_body__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(region__icontains=search_query)
        )

    stations_qs = stations_qs.order_by('-created_at')

    paginator = Paginator(stations_qs, page_size)

    try:
        paginated = paginator.page(page_number)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)

    serializer = StationComplianceSerializer(paginated, many=True)
    data['stations'] = serializer.data
    data['pagination'] = {
        'page_number': paginated.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'next': paginated.next_page_number() if paginated.has_next() else None,
        'previous': paginated.previous_page_number() if paginated.has_previous() else None,
    }

    payload['message'] = 'Successful'
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def verify_station(request):
    """Verify or reject a station (admin only)"""
    payload = {}
    errors = {}

    # Check if user is admin
    if not request.user.is_staff:
        payload['message'] = 'Permission denied. Admin access required.'
        return Response(payload, status=status.HTTP_403_FORBIDDEN)

    station_id = request.data.get('station_id', '')
    verification_status = request.data.get('verification_status', '')  # 'verified', 'rejected', 'suspended'
    verification_notes = request.data.get('verification_notes', '')

    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not verification_status:
        errors['verification_status'] = ['Verification status is required.']
    if verification_status not in ['verified', 'rejected', 'suspended']:
        errors['verification_status'] = ['Invalid verification status.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station does not exist.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Update verification status
    station.verification_status = verification_status
    station.verified_by = request.user
    station.verified_at = timezone.now()
    station.verification_notes = verification_notes

    # If verified, activate the station
    if verification_status == 'verified':
        station.active = True
    elif verification_status in ['rejected', 'suspended']:
        station.active = False

    station.save()

    serializer = StationDetailsSerializer(station)
    payload['message'] = f'Station {verification_status} successfully'
    payload['data'] = serializer.data

    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_station_compliance_report(request):
    """Generate compliance report for a station"""
    payload = {}
    errors = {}

    station_id = request.query_params.get('station_id')

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

    # Generate compliance report data
    compliance_data = {
        'station_info': StationComplianceSerializer(station).data,
        'staff_count': station.station_staff.filter(is_archived=False, active=True).count(),
        'stream_links_count': station.station_links.filter(is_archived=False, active=True).count(),
        'compliance_checklist': {
            'license_number_provided': bool(station.license_number),
            'regulatory_body_specified': bool(station.regulatory_body),
            'compliance_contact_provided': bool(station.compliance_contact_name and station.compliance_contact_email),
            'operating_hours_specified': bool(station.operating_hours_start and station.operating_hours_end),
            'broadcast_frequency_provided': bool(station.broadcast_frequency),
            'staff_assigned': station.station_staff.filter(is_archived=False, active=True).exists(),
            'stream_links_configured': station.station_links.filter(is_archived=False, active=True).exists(),
        }
    }

    # Calculate compliance score
    checklist = compliance_data['compliance_checklist']
    total_items = len(checklist)
    completed_items = sum(1 for item in checklist.values() if item)
    compliance_score = (completed_items / total_items) * 100 if total_items > 0 else 0

    compliance_data['compliance_score'] = round(compliance_score, 2)
    compliance_data['completed_items'] = completed_items
    compliance_data['total_items'] = total_items

    payload['message'] = 'Compliance report generated successfully'
    payload['data'] = compliance_data

    return Response(payload, status=status.HTTP_200_OK)