import uuid
import json
import logging
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from accounts.models import AuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(MiddlewareMixin):
    """Middleware to log all user actions and system events"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Generate trace ID for request correlation
        request.trace_id = str(uuid.uuid4())
        request.start_time = timezone.now()
        
        # Skip logging for certain paths
        skip_paths = ['/admin/', '/static/', '/media/', '/health/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        return None
    
    def process_response(self, request, response):
        # Skip logging for certain paths
        skip_paths = ['/admin/', '/static/', '/media/', '/health/']
        if any(request.path.startswith(path) for path in skip_paths):
            return response
        
        try:
            # Get user info
            user = getattr(request, 'user', None)
            if user and user.is_authenticated:
                user_obj = user
            else:
                user_obj = None
            
            # Get client IP
            ip_address = self.get_client_ip(request)
            
            # Get request data (be careful with sensitive data)
            request_data = {}
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    if hasattr(request, 'data'):
                        request_data = dict(request.data)
                    elif request.content_type == 'application/json':
                        request_data = json.loads(request.body.decode('utf-8'))
                    
                    # Remove sensitive fields
                    sensitive_fields = ['password', 'password2', 'token', 'secret']
                    for field in sensitive_fields:
                        if field in request_data:
                            request_data[field] = '[REDACTED]'
                except:
                    request_data = {}
            
            # Get response data for errors
            response_data = {}
            if response.status_code >= 400:
                try:
                    if hasattr(response, 'data'):
                        response_data = response.data
                    elif response.content:
                        response_data = json.loads(response.content.decode('utf-8'))
                except:
                    response_data = {'error': 'Response parsing failed'}
            
            # Create audit log entry
            AuditLog.objects.create(
                user=user_obj,
                action=f"{request.method} {request.path}",
                resource_type=self.extract_resource_type(request.path),
                resource_id=self.extract_resource_id(request.path),
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_data=request_data,
                response_data=response_data,
                status_code=response.status_code,
                trace_id=getattr(request, 'trace_id', None)
            )
            
        except Exception as e:
            logger.error(f"Audit logging failed: {str(e)}")
        
        return response
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def extract_resource_type(self, path):
        """Extract resource type from URL path"""
        path_parts = path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'api':
            return path_parts[1]
        return None
    
    def extract_resource_id(self, path):
        """Extract resource ID from URL path"""
        path_parts = path.strip('/').split('/')
        for part in path_parts:
            if part.isdigit() or (len(part) > 10 and '-' in part):  # UUID or numeric ID
                return part
        return None


class RateLimitMiddleware(MiddlewareMixin):
    """Simple rate limiting middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Skip rate limiting for certain paths
        skip_paths = ['/admin/', '/static/', '/media/', '/health/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Get client IP
        ip_address = self.get_client_ip(request)
        
        # Simple rate limiting logic (can be enhanced with Redis)
        # For now, just log excessive requests
        if self.is_rate_limited(ip_address, request):
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }, status=429)
        
        return None
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_rate_limited(self, ip_address, request):
        """Check if IP is rate limited (simplified implementation)"""
        # This is a basic implementation
        # In production, use Redis with sliding window or token bucket
        from django.core.cache import cache
        
        cache_key = f"rate_limit:{ip_address}"
        current_requests = cache.get(cache_key, 0)
        
        # Allow 100 requests per minute per IP
        if current_requests >= 100:
            return True
        
        # Increment counter
        cache.set(cache_key, current_requests + 1, 60)  # 60 seconds TTL
        return False


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses"""
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add HSTS header for HTTPS
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response