from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import json

from .services import analytics_aggregator
from .models import AnalyticsExport, UserAnalyticsPreference
from .tasks import generate_analytics_export
from artists.models import Artist
from stations.models import Station
from publishers.models import PublisherProfile


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def artist_analytics(request, artist_id=None):
    """Get analytics data for an artist"""
    try:
        # If no artist_id provided, get current user's artist
        if not artist_id:
            try:
                artist = request.user.artists.filter(active=True).first()
                if not artist:
                    return Response(
                        {'error': 'No active artist profile found'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
                artist_id = artist.artist_id
            except:
                return Response(
                    {'error': 'Artist profile not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Parse date range
        date_range = parse_date_range(request)
        
        # Get analytics data
        analytics_data = analytics_aggregator.get_artist_analytics(artist_id, date_range)
        
        if not analytics_data:
            return Response(
                {'error': 'Artist not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve analytics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_analytics(request, publisher_id=None):
    """Get analytics data for a publisher"""
    try:
        # If no publisher_id provided, get current user's publisher
        if not publisher_id:
            try:
                if hasattr(request.user, 'publisher_profile'):
                    publisher_id = request.user.publisher_profile.id
                else:
                    return Response(
                        {'error': 'No publisher profile found'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
            except:
                return Response(
                    {'error': 'Publisher profile not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Parse date range
        date_range = parse_date_range(request)
        
        # Get analytics data
        analytics_data = analytics_aggregator.get_publisher_analytics(publisher_id, date_range)
        
        if not analytics_data:
            return Response(
                {'error': 'Publisher not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve analytics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def station_analytics(request, station_id=None):
    """Get analytics data for a station"""
    try:
        # If no station_id provided, get current user's station
        if not station_id:
            try:
                station = request.user.station_user.filter(active=True).first()
                if not station:
                    return Response(
                        {'error': 'No active station profile found'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
                station_id = station.station_id
            except:
                return Response(
                    {'error': 'Station profile not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Parse date range
        date_range = parse_date_range(request)
        
        # Get analytics data
        analytics_data = analytics_aggregator.get_station_analytics(station_id, date_range)
        
        if not analytics_data:
            return Response(
                {'error': 'Station not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve analytics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_analytics(request):
    """Get platform-wide analytics for administrators"""
    try:
        # Check if user is admin
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'error': 'Admin access required'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Parse date range
        date_range = parse_date_range(request)
        
        # Get analytics data
        analytics_data = analytics_aggregator.get_admin_analytics(date_range)
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve analytics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def realtime_metrics(request):
    """Get real-time metrics"""
    try:
        metric_names = request.GET.getlist('metrics', [
            'active_detections',
            'processing_queue',
            'revenue_today',
            'plays_today'
        ])
        
        # Get filters based on user type
        filters = {}
        if hasattr(request.user, 'artists') and request.user.artists.exists():
            artist = request.user.artists.filter(active=True).first()
            if artist:
                filters['artist_id'] = artist.artist_id
        elif hasattr(request.user, 'station_user') and request.user.station_user.exists():
            station = request.user.station_user.filter(active=True).first()
            if station:
                filters['station_id'] = station.station_id
        
        metrics = analytics_aggregator.get_realtime_metrics(metric_names, **filters)
        
        return Response({
            'metrics': metrics,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve real-time metrics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_export(request):
    """Request analytics data export"""
    try:
        data = request.data
        export_type = data.get('export_type')
        export_format = data.get('export_format', 'csv')
        parameters = data.get('parameters', {})
        
        # Validate export type
        valid_types = [choice[0] for choice in AnalyticsExport.EXPORT_TYPES]
        if export_type not in valid_types:
            return Response(
                {'error': 'Invalid export type'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate export format
        valid_formats = [choice[0] for choice in AnalyticsExport.EXPORT_FORMATS]
        if export_format not in valid_formats:
            return Response(
                {'error': 'Invalid export format'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse date range from parameters
        date_range_start = None
        date_range_end = None
        if 'date_range' in parameters:
            try:
                date_range_start = datetime.fromisoformat(parameters['date_range']['start'])
                date_range_end = datetime.fromisoformat(parameters['date_range']['end'])
            except (KeyError, ValueError):
                pass
        
        # Create export request
        export_request = AnalyticsExport.objects.create(
            user=request.user,
            export_type=export_type,
            export_format=export_format,
            parameters=parameters,
            date_range_start=date_range_start,
            date_range_end=date_range_end
        )
        
        # Queue export task
        generate_analytics_export.delay(export_request.export_id)
        
        return Response({
            'export_id': export_request.export_id,
            'status': export_request.status,
            'message': 'Export request queued successfully'
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to request export: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_status(request, export_id):
    """Get status of an export request"""
    try:
        export_request = AnalyticsExport.objects.get(
            export_id=export_id,
            user=request.user
        )
        
        return Response({
            'export_id': export_request.export_id,
            'status': export_request.status,
            'progress_percentage': export_request.progress_percentage,
            'file_size_bytes': export_request.file_size_bytes,
            'requested_at': export_request.requested_at,
            'completed_at': export_request.completed_at,
            'expires_at': export_request.expires_at,
            'error_message': export_request.error_message
        })
        
    except AnalyticsExport.DoesNotExist:
        return Response(
            {'error': 'Export request not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_export(request, export_id):
    """Download completed export file"""
    try:
        export_request = AnalyticsExport.objects.get(
            export_id=export_id,
            user=request.user
        )
        
        if export_request.status != 'completed':
            return Response(
                {'error': 'Export not completed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if export_request.is_expired():
            return Response(
                {'error': 'Export has expired'}, 
                status=status.HTTP_410_GONE
            )
        
        # Increment download count
        export_request.increment_download()
        
        # Return file download response
        # This would typically serve the file from storage
        return Response({
            'download_url': f'/media/exports/{export_request.file_path}',
            'file_size': export_request.file_size_bytes,
            'expires_at': export_request.expires_at
        })
        
    except AnalyticsExport.DoesNotExist:
        return Response(
            {'error': 'Export request not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_preferences(request):
    """Get or update user analytics preferences"""
    try:
        preferences, created = UserAnalyticsPreference.objects.get_or_create(
            user=request.user
        )
        
        if request.method == 'GET':
            return Response({
                'default_date_range': preferences.default_date_range,
                'dashboard_layout': preferences.dashboard_layout,
                'favorite_metrics': preferences.favorite_metrics,
                'email_reports': preferences.email_reports,
                'report_frequency': preferences.report_frequency,
                'preferred_export_format': preferences.preferred_export_format
            })
        
        elif request.method == 'POST':
            data = request.data
            
            # Update preferences
            if 'default_date_range' in data:
                preferences.default_date_range = data['default_date_range']
            if 'dashboard_layout' in data:
                preferences.dashboard_layout = data['dashboard_layout']
            if 'favorite_metrics' in data:
                preferences.favorite_metrics = data['favorite_metrics']
            if 'email_reports' in data:
                preferences.email_reports = data['email_reports']
            if 'report_frequency' in data:
                preferences.report_frequency = data['report_frequency']
            if 'preferred_export_format' in data:
                preferences.preferred_export_format = data['preferred_export_format']
            
            preferences.save()
            
            return Response({'message': 'Preferences updated successfully'})
        
    except Exception as e:
        return Response(
            {'error': f'Failed to handle preferences: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def comparative_analytics(request):
    """Get comparative analytics data"""
    try:
        comparison_type = request.GET.get('type', 'period')  # period, peer, regional
        
        if comparison_type == 'period':
            return get_period_comparison(request)
        elif comparison_type == 'peer':
            return get_peer_comparison(request)
        elif comparison_type == 'regional':
            return get_regional_comparison(request)
        else:
            return Response(
                {'error': 'Invalid comparison type'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve comparative analytics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def parse_date_range(request):
    """Parse date range from request parameters"""
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    range_preset = request.GET.get('range', '30d')
    
    if start_date_str and end_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError:
            # Fallback to preset range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)
    else:
        # Use preset range
        end_date = timezone.now()
        if range_preset == '7d':
            start_date = end_date - timedelta(days=7)
        elif range_preset == '30d':
            start_date = end_date - timedelta(days=30)
        elif range_preset == '90d':
            start_date = end_date - timedelta(days=90)
        elif range_preset == '1y':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
    
    return (start_date, end_date)


def get_period_comparison(request):
    """Get period-over-period comparison"""
    # Implementation for period comparison
    return Response({'message': 'Period comparison not yet implemented'})


def get_peer_comparison(request):
    """Get peer comparison analytics"""
    # Implementation for peer comparison
    return Response({'message': 'Peer comparison not yet implemented'})


def get_regional_comparison(request):
    """Get regional comparison analytics"""
    # Implementation for regional comparison
    return Response({'message': 'Regional comparison not yet implemented'})