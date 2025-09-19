"""
Centralized error logging and monitoring system for ZamIO platform
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
import json


class ErrorLogger:
    """
    Centralized error logging with structured data and monitoring capabilities
    """
    
    def __init__(self):
        self.logger = logging.getLogger('zamio.errors')
        
    def log_error(self, 
                  error: Exception, 
                  context: Dict[str, Any] = None,
                  user_id: str = None,
                  trace_id: str = None,
                  severity: str = 'error') -> str:
        """
        Log an error with structured data and return trace ID
        
        Args:
            error: The exception that occurred
            context: Additional context information
            user_id: ID of the user who encountered the error
            trace_id: Existing trace ID or generate new one
            severity: Error severity level (debug, info, warning, error, critical)
            
        Returns:
            str: Trace ID for error correlation
        """
        if not trace_id:
            trace_id = str(uuid.uuid4())
            
        error_data = {
            'trace_id': trace_id,
            'timestamp': datetime.now().isoformat(),
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'user_id': user_id,
            'severity': severity,
            'context': context or {}
        }
        
        # Add stack trace for debugging
        import traceback
        error_data['stack_trace'] = traceback.format_exc()
        
        # Log with appropriate level
        log_method = getattr(self.logger, severity, self.logger.error)
        log_method(
            f"Error: {error.__class__.__name__}: {str(error)}",
            extra=error_data
        )
        
        # Store in cache for recent error tracking
        self._cache_error(trace_id, error_data)
        
        # Send to monitoring service if configured
        self._send_to_monitoring(error_data)
        
        return trace_id
    
    def log_api_error(self, 
                      error: Exception,
                      request_data: Dict[str, Any] = None,
                      user_id: str = None,
                      trace_id: str = None) -> str:
        """
        Log API-specific errors with request context
        """
        context = {
            'error_category': 'api_error',
            'request_data': request_data or {}
        }
        
        return self.log_error(error, context, user_id, trace_id)
    
    def log_fingerprint_error(self, 
                             error: Exception,
                             audio_file_info: Dict[str, Any] = None,
                             user_id: str = None,
                             trace_id: str = None) -> str:
        """
        Log fingerprinting-specific errors
        """
        context = {
            'error_category': 'fingerprint_processing',
            'audio_file_info': audio_file_info or {}
        }
        
        return self.log_error(error, context, user_id, trace_id, 'warning')
    
    def log_royalty_error(self, 
                         error: Exception,
                         calculation_data: Dict[str, Any] = None,
                         user_id: str = None,
                         trace_id: str = None) -> str:
        """
        Log royalty calculation errors
        """
        context = {
            'error_category': 'royalty_calculation',
            'calculation_data': calculation_data or {}
        }
        
        return self.log_error(error, context, user_id, trace_id, 'error')
    
    def log_external_service_error(self, 
                                  error: Exception,
                                  service_name: str,
                                  request_details: Dict[str, Any] = None,
                                  user_id: str = None,
                                  trace_id: str = None) -> str:
        """
        Log external service integration errors
        """
        context = {
            'error_category': 'external_service',
            'service_name': service_name,
            'request_details': request_details or {}
        }
        
        return self.log_error(error, context, user_id, trace_id, 'warning')
    
    def get_error_by_trace_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve error details by trace ID from cache
        """
        cache_key = f"error_trace:{trace_id}"
        return cache.get(cache_key)
    
    def get_recent_errors(self, user_id: str = None, limit: int = 10) -> list:
        """
        Get recent errors, optionally filtered by user
        """
        cache_key = f"recent_errors:{user_id}" if user_id else "recent_errors:all"
        errors = cache.get(cache_key, [])
        return errors[:limit]
    
    def _cache_error(self, trace_id: str, error_data: Dict[str, Any]):
        """
        Cache error data for quick retrieval
        """
        # Store individual error by trace ID
        cache_key = f"error_trace:{trace_id}"
        cache.set(cache_key, error_data, timeout=86400)  # 24 hours
        
        # Add to recent errors list
        recent_errors_key = "recent_errors:all"
        recent_errors = cache.get(recent_errors_key, [])
        recent_errors.insert(0, {
            'trace_id': trace_id,
            'timestamp': error_data['timestamp'],
            'error_type': error_data['error_type'],
            'error_message': error_data['error_message'],
            'user_id': error_data.get('user_id'),
            'severity': error_data['severity']
        })
        
        # Keep only last 100 errors
        recent_errors = recent_errors[:100]
        cache.set(recent_errors_key, recent_errors, timeout=86400)
        
        # User-specific recent errors
        if error_data.get('user_id'):
            user_errors_key = f"recent_errors:{error_data['user_id']}"
            user_errors = cache.get(user_errors_key, [])
            user_errors.insert(0, {
                'trace_id': trace_id,
                'timestamp': error_data['timestamp'],
                'error_type': error_data['error_type'],
                'error_message': error_data['error_message'],
                'severity': error_data['severity']
            })
            user_errors = user_errors[:50]  # Keep last 50 per user
            cache.set(user_errors_key, user_errors, timeout=86400)
    
    def _send_to_monitoring(self, error_data: Dict[str, Any]):
        """
        Send error data to external monitoring service
        """
        # This would integrate with services like Sentry, DataDog, etc.
        # For now, we'll just log it as a placeholder
        if settings.DEBUG:
            return
            
        # Example integration point
        monitoring_service = getattr(settings, 'ERROR_MONITORING_SERVICE', None)
        if monitoring_service:
            try:
                # Send to monitoring service
                pass
            except Exception as e:
                # Don't let monitoring errors break the application
                self.logger.warning(f"Failed to send error to monitoring service: {e}")


class ErrorMetrics:
    """
    Error metrics and analytics for monitoring system health
    """
    
    def __init__(self):
        self.cache_prefix = "error_metrics"
    
    def increment_error_count(self, error_type: str, user_id: str = None):
        """
        Increment error count for metrics
        """
        # Global error count
        global_key = f"{self.cache_prefix}:count:{error_type}"
        current_count = cache.get(global_key, 0)
        cache.set(global_key, current_count + 1, timeout=86400)
        
        # User-specific error count
        if user_id:
            user_key = f"{self.cache_prefix}:user:{user_id}:{error_type}"
            user_count = cache.get(user_key, 0)
            cache.set(user_key, user_count + 1, timeout=86400)
    
    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get error statistics for monitoring dashboard
        """
        # This would aggregate error data for admin dashboard
        return {
            'total_errors_24h': self._get_total_errors_24h(),
            'error_types': self._get_error_type_breakdown(),
            'top_error_users': self._get_top_error_users(),
            'error_trends': self._get_error_trends()
        }
    
    def _get_total_errors_24h(self) -> int:
        """Get total error count in last 24 hours"""
        # Implementation would query cache or database
        return 0
    
    def _get_error_type_breakdown(self) -> Dict[str, int]:
        """Get breakdown of errors by type"""
        return {}
    
    def _get_top_error_users(self) -> list:
        """Get users with most errors"""
        return []
    
    def _get_error_trends(self) -> Dict[str, Any]:
        """Get error trends over time"""
        return {}


# Global instances
error_logger = ErrorLogger()
error_metrics = ErrorMetrics()