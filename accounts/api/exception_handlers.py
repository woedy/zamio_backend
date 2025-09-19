import uuid
import logging
from datetime import datetime
from django.http import Http404
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import ValidationError, APIException

logger = logging.getLogger(__name__)


class APIErrorResponse:
    """
    Standardized API error response class
    """
    def __init__(self, code: str, message: str, details: dict = None, trace_id: str = None):
        self.code = code
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'error': {
                'code': self.code,
                'message': self.message,
                'details': self.details,
                'trace_id': self.trace_id,
                'timestamp': self.timestamp
            }
        }


class CustomAPIException(APIException):
    """
    Custom API exception with error code support
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'An unexpected error occurred.'
    default_code = 'INTERNAL_SERVER_ERROR'
    
    def __init__(self, detail=None, code=None, status_code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
        if status_code is not None:
            self.status_code = status_code
        
        self.detail = detail
        self.code = code


class FingerprintProcessingError(CustomAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Audio fingerprinting failed. Please try again with a different audio file.'
    default_code = 'FINGERPRINT_PROCESSING_ERROR'


class RoyaltyCalculationError(CustomAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Royalty calculation failed. Please contact support.'
    default_code = 'ROYALTY_CALCULATION_ERROR'


class ExternalServiceError(CustomAPIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'External service temporarily unavailable. Please try again later.'
    default_code = 'EXTERNAL_SERVICE_ERROR'


def custom_exception_handler(exc, context):
    """
    Enhanced custom exception handler that provides consistent error responses
    with comprehensive logging and user-friendly messages
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Generate trace ID for error correlation
    trace_id = str(uuid.uuid4())
    
    # Extract request information
    request = context.get('request')
    user = getattr(request, 'user', None) if request else None
    view = context.get('view')
    
    # Enhanced logging with structured data
    log_data = {
        'trace_id': trace_id,
        'exception_type': exc.__class__.__name__,
        'exception_message': str(exc),
        'user': user.email if user and user.is_authenticated else 'Anonymous',
        'user_id': getattr(user, 'user_id', None) if user and user.is_authenticated else None,
        'path': request.path if request else 'Unknown',
        'method': request.method if request else 'Unknown',
        'view_name': view.__class__.__name__ if view else 'Unknown',
        'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown') if request else 'Unknown',
        'ip_address': get_client_ip(request) if request else 'Unknown',
    }
    
    # Log with appropriate level based on exception type
    if isinstance(exc, (ValidationError, DjangoValidationError)):
        logger.warning(f"Validation Error: {str(exc)}", extra=log_data)
    elif isinstance(exc, (PermissionDenied, InvalidToken, TokenError)):
        logger.warning(f"Security Error: {str(exc)}", extra=log_data)
    else:
        logger.error(f"API Exception: {str(exc)}", extra=log_data)
    
    if response is not None:
        # Use APIErrorResponse for consistent formatting
        error_response = APIErrorResponse(
            code=get_error_code(exc),
            message=get_user_friendly_message(exc, response.data),
            details=get_error_details(response.data),
            trace_id=trace_id
        )
        
        response.data = error_response.to_dict()
    else:
        # Handle exceptions not handled by DRF
        error_response = handle_unhandled_exception(exc, trace_id)
        response = Response(error_response.to_dict(), status=error_response.details.get('status_code', 500))
    
    return response


def handle_unhandled_exception(exc, trace_id):
    """
    Handle exceptions not caught by DRF's default handler
    """
    if isinstance(exc, Http404):
        return APIErrorResponse(
            code='RESOURCE_NOT_FOUND',
            message='The requested resource was not found.',
            trace_id=trace_id,
            details={'status_code': 404}
        )
    
    elif isinstance(exc, PermissionDenied):
        return APIErrorResponse(
            code='PERMISSION_DENIED',
            message='You do not have permission to perform this action.',
            trace_id=trace_id,
            details={'status_code': 403}
        )
    
    elif isinstance(exc, (InvalidToken, TokenError)):
        return APIErrorResponse(
            code='AUTHENTICATION_ERROR',
            message='Invalid or expired authentication token. Please log in again.',
            trace_id=trace_id,
            details={'status_code': 401}
        )
    
    elif isinstance(exc, DjangoValidationError):
        return APIErrorResponse(
            code='VALIDATION_ERROR',
            message='Input validation failed. Please check your data and try again.',
            trace_id=trace_id,
            details={'status_code': 400, 'validation_errors': exc.message_dict if hasattr(exc, 'message_dict') else str(exc)}
        )
    
    else:
        # Generic server error
        return APIErrorResponse(
            code='INTERNAL_SERVER_ERROR',
            message='An unexpected error occurred. Please try again later.',
            trace_id=trace_id,
            details={'status_code': 500}
        )


def get_client_ip(request):
    """
    Extract client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_error_code(exc):
    """
    Enhanced mapping of exception types to standardized error codes
    """
    # Check if it's a custom exception with its own code
    if hasattr(exc, 'code') and exc.code:
        return exc.code
    
    error_code_map = {
        'ValidationError': 'VALIDATION_ERROR',
        'AuthenticationFailed': 'AUTHENTICATION_ERROR',
        'NotAuthenticated': 'AUTHENTICATION_ERROR',
        'PermissionDenied': 'PERMISSION_DENIED',
        'NotFound': 'RESOURCE_NOT_FOUND',
        'MethodNotAllowed': 'METHOD_NOT_ALLOWED',
        'Throttled': 'RATE_LIMIT_EXCEEDED',
        'ParseError': 'PARSE_ERROR',
        'UnsupportedMediaType': 'UNSUPPORTED_MEDIA_TYPE',
        'InvalidToken': 'AUTHENTICATION_ERROR',
        'TokenError': 'AUTHENTICATION_ERROR',
        'Http404': 'RESOURCE_NOT_FOUND',
        'DjangoValidationError': 'VALIDATION_ERROR',
        'FingerprintProcessingError': 'FINGERPRINT_PROCESSING_ERROR',
        'RoyaltyCalculationError': 'ROYALTY_CALCULATION_ERROR',
        'ExternalServiceError': 'EXTERNAL_SERVICE_ERROR',
        'ConnectionError': 'EXTERNAL_SERVICE_ERROR',
        'TimeoutError': 'EXTERNAL_SERVICE_ERROR',
        'RequestException': 'EXTERNAL_SERVICE_ERROR',
    }
    
    return error_code_map.get(exc.__class__.__name__, 'UNKNOWN_ERROR')


def get_user_friendly_message(exc, response_data):
    """
    Generate user-friendly error messages with actionable guidance
    """
    # Check if it's a custom exception with predefined message
    if hasattr(exc, 'detail') and exc.detail:
        return str(exc.detail)
    
    # Map error codes to user-friendly messages
    error_code = get_error_code(exc)
    user_friendly_messages = {
        'VALIDATION_ERROR': 'Please check your input and try again.',
        'AUTHENTICATION_ERROR': 'Please log in again to continue.',
        'PERMISSION_DENIED': 'You don\'t have permission to perform this action.',
        'RESOURCE_NOT_FOUND': 'The requested item could not be found.',
        'METHOD_NOT_ALLOWED': 'This action is not allowed.',
        'RATE_LIMIT_EXCEEDED': 'Too many requests. Please wait a moment and try again.',
        'PARSE_ERROR': 'Invalid data format. Please check your input.',
        'UNSUPPORTED_MEDIA_TYPE': 'Unsupported file type. Please use a supported format.',
        'FINGERPRINT_PROCESSING_ERROR': 'Audio processing failed. Please try with a different audio file.',
        'ROYALTY_CALCULATION_ERROR': 'Royalty calculation failed. Please contact support if this persists.',
        'EXTERNAL_SERVICE_ERROR': 'Service temporarily unavailable. Please try again in a few minutes.',
    }
    
    # Try to get user-friendly message based on error code
    if error_code in user_friendly_messages:
        base_message = user_friendly_messages[error_code]
        
        # Add specific field validation details if available
        if isinstance(response_data, dict) and error_code == 'VALIDATION_ERROR':
            field_details = get_validation_field_details(response_data)
            if field_details:
                return f"{base_message} {field_details}"
        
        return base_message
    
    # Fallback to processing response data
    if isinstance(response_data, dict):
        # Handle validation errors
        if 'detail' in response_data:
            return str(response_data['detail'])
        
        # Handle field validation errors
        if any(key for key in response_data.keys() if key != 'detail'):
            field_errors = get_validation_field_details(response_data)
            return f"Please check your input: {field_errors}"
    
    elif isinstance(response_data, list) and response_data:
        return str(response_data[0])
    
    # Final fallback to exception message
    return str(exc)


def get_validation_field_details(response_data):
    """
    Extract and format field validation error details
    """
    field_errors = []
    for field, errors in response_data.items():
        if field == 'detail':
            continue
            
        # Convert field name to user-friendly format
        friendly_field = field.replace('_', ' ').title()
        
        if isinstance(errors, list):
            error_messages = [str(e) for e in errors]
            field_errors.append(f"{friendly_field}: {', '.join(error_messages)}")
        else:
            field_errors.append(f"{friendly_field}: {str(errors)}")
    
    return '; '.join(field_errors) if field_errors else ''


def get_error_details(response_data):
    """
    Extract additional error details for debugging and client-side handling
    """
    details = {}
    
    if isinstance(response_data, dict):
        # Include field-level validation errors for client-side form handling
        field_errors = {}
        for field, errors in response_data.items():
            if field != 'detail':
                if isinstance(errors, list):
                    field_errors[field] = [str(e) for e in errors]
                else:
                    field_errors[field] = [str(errors)]
        
        if field_errors:
            details['field_errors'] = field_errors
        
        # Include any other relevant details
        if 'detail' in response_data:
            details['original_detail'] = str(response_data['detail'])
    
    elif isinstance(response_data, list):
        details['errors'] = [str(e) for e in response_data]
    
    return details