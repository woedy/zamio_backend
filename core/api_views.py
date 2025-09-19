"""
Core API views for error logging and system health
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging

from .error_logging import error_logger, error_metrics

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_frontend_error(request):
    """
    Log frontend errors for monitoring and debugging
    """
    try:
        data = request.data
        
        # Extract error information
        error_info = {
            'message': data.get('message', 'Unknown error'),
            'stack': data.get('stack', ''),
            'component_stack': data.get('componentStack', ''),
            'user_agent': data.get('userAgent', ''),
            'url': data.get('url', ''),
            'timestamp': data.get('timestamp', ''),
            'trace_id': data.get('trace_id', ''),
            'user_id': request.user.user_id if hasattr(request.user, 'user_id') else None,
            'user_email': request.user.email if request.user.is_authenticated else None,
            'error_type': data.get('error_type', 'frontend_error'),
            'severity': data.get('severity', 'error')
        }
        
        # Create a mock exception for logging
        class FrontendError(Exception):
            def __init__(self, message):
                self.message = message
                super().__init__(message)
        
        frontend_error = FrontendError(error_info['message'])
        
        # Log the error
        trace_id = error_logger.log_error(
            error=frontend_error,
            context={
                'error_category': 'frontend_error',
                'frontend_data': error_info
            },
            user_id=error_info['user_id'],
            trace_id=error_info['trace_id'],
            severity=error_info['severity']
        )
        
        # Update metrics
        error_metrics.increment_error_count(
            error_type='frontend_error',
            user_id=error_info['user_id']
        )
        
        return Response({
            'success': True,
            'trace_id': trace_id,
            'message': 'Error logged successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to log frontend error: {str(e)}")
        return Response({
            'error': {
                'code': 'LOGGING_ERROR',
                'message': 'Failed to log error'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring system status
    """
    try:
        # Basic health checks
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'checks': {
                'database': check_database_health(),
                'cache': check_cache_health(),
                'celery': check_celery_health()
            }
        }
        
        # Determine overall status
        all_healthy = all(check['status'] == 'healthy' for check in health_status['checks'].values())
        if not all_healthy:
            health_status['status'] = 'degraded'
            return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return Response(health_status, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_error_by_trace_id(request, trace_id):
    """
    Retrieve error details by trace ID for support purposes
    """
    try:
        # Check if user has permission to view errors
        if not request.user.is_staff and not request.user.user_type == 'Admin':
            return Response({
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': 'You do not have permission to view error details'
                }
            }, status=status.HTTP_403_FORBIDDEN)
        
        error_data = error_logger.get_error_by_trace_id(trace_id)
        
        if not error_data:
            return Response({
                'error': {
                    'code': 'RESOURCE_NOT_FOUND',
                    'message': 'Error not found'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'error_data': error_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to retrieve error: {str(e)}")
        return Response({
            'error': {
                'code': 'INTERNAL_SERVER_ERROR',
                'message': 'Failed to retrieve error details'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_error_metrics(request):
    """
    Get error metrics for admin dashboard
    """
    try:
        # Check if user has permission to view metrics
        if not request.user.is_staff and not request.user.user_type == 'Admin':
            return Response({
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': 'You do not have permission to view error metrics'
                }
            }, status=status.HTTP_403_FORBIDDEN)
        
        metrics = error_metrics.get_error_stats()
        
        return Response({
            'success': True,
            'metrics': metrics
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to retrieve error metrics: {str(e)}")
        return Response({
            'error': {
                'code': 'INTERNAL_SERVER_ERROR',
                'message': 'Failed to retrieve error metrics'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def check_database_health():
    """Check database connectivity"""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return {'status': 'healthy', 'message': 'Database connection OK'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Database error: {str(e)}'}


def check_cache_health():
    """Check cache connectivity"""
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        if result == 'ok':
            return {'status': 'healthy', 'message': 'Cache connection OK'}
        else:
            return {'status': 'unhealthy', 'message': 'Cache not responding correctly'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Cache error: {str(e)}'}


def check_celery_health():
    """Check Celery worker status"""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        if stats:
            return {'status': 'healthy', 'message': 'Celery workers active'}
        else:
            return {'status': 'unhealthy', 'message': 'No Celery workers found'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Celery error: {str(e)}'}


# Import timezone after Django setup
from django.utils import timezone