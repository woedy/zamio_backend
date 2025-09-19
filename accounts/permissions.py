from functools import wraps
from django.contrib.auth import get_user_model
from django.db import models
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        return obj.user == request.user


class HasUserPermission(permissions.BasePermission):
    """
    Check if user has specific permission
    """
    def __init__(self, permission_name):
        self.permission_name = permission_name
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has the specific permission
        return request.user.user_permissions.filter(
            permission=self.permission_name,
            is_active=True
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        ).exists()


class RoleBasedPermission(permissions.BasePermission):
    """
    Permission class that checks user roles
    """
    def __init__(self, allowed_roles):
        self.allowed_roles = allowed_roles if isinstance(allowed_roles, list) else [allowed_roles]
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.user_type in self.allowed_roles


def require_permission(permission_name):
    """
    Decorator to require specific permission for view functions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required',
                    'code': 'AUTHENTICATION_ERROR'
                }, status=401)
            
            # Check if user has the specific permission
            has_permission = request.user.user_permissions.filter(
                permission=permission_name,
                is_active=True
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            ).exists()
            
            if not has_permission:
                return JsonResponse({
                    'error': f'Permission denied. Required permission: {permission_name}',
                    'code': 'PERMISSION_DENIED'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(allowed_roles):
    """
    Decorator to require specific user roles for view functions
    """
    if not isinstance(allowed_roles, list):
        allowed_roles = [allowed_roles]
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required',
                    'code': 'AUTHENTICATION_ERROR'
                }, status=401)
            
            if request.user.user_type not in allowed_roles:
                return JsonResponse({
                    'error': f'Access denied. Required roles: {", ".join(allowed_roles)}',
                    'code': 'PERMISSION_DENIED'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_self_or_admin(view_func):
    """
    Decorator to allow access only to the user themselves or admin users
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'AUTHENTICATION_ERROR'
            }, status=401)
        
        # Get user_id from URL parameters or request data
        target_user_id = kwargs.get('user_id') or request.data.get('user_id')
        
        # Allow if user is admin or accessing their own data
        if (request.user.user_type == 'Admin' or 
            request.user.user_id == target_user_id):
            return view_func(request, *args, **kwargs)
        
        return JsonResponse({
            'error': 'Access denied. You can only access your own data.',
            'code': 'PERMISSION_DENIED'
        }, status=403)
    return wrapper


def require_kyc_verified(view_func):
    """
    Decorator to require KYC verification for certain actions
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'AUTHENTICATION_ERROR'
            }, status=401)
        
        if request.user.kyc_status != 'verified':
            return JsonResponse({
                'error': 'KYC verification required for this action',
                'code': 'KYC_VERIFICATION_REQUIRED',
                'kyc_status': request.user.kyc_status
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper


# DRF Permission Classes
class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 'Admin')


class IsArtistUser(permissions.BasePermission):
    """
    Allows access only to artist users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 'Artist')


class IsPublisherUser(permissions.BasePermission):
    """
    Allows access only to publisher users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 'Publisher')


class IsStationUser(permissions.BasePermission):
    """
    Allows access only to station users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 'Station')


class IsKYCVerified(permissions.BasePermission):
    """
    Allows access only to KYC verified users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.kyc_status == 'verified'
        )


class IsAdminOrMediator(permissions.BasePermission):
    """
    Allows access only to admin or mediator users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type in ['Admin', 'Mediator']
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allows access to object owner or admin users.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users have full access
        if request.user.user_type == 'Admin':
            return True
        
        # Check if user is the owner (works for objects with submitted_by, user, or owner field)
        owner_fields = ['submitted_by', 'user', 'owner', 'created_by']
        for field in owner_fields:
            if hasattr(obj, field):
                owner = getattr(obj, field)
                if owner == request.user:
                    return True
        
        return False


class CanAccessDispute(permissions.BasePermission):
    """
    Custom permission for dispute access based on user role and relationship to dispute.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and mediator users have full access
        if request.user.user_type in ['Admin', 'Mediator']:
            return True
        
        # Dispute submitter has access
        if obj.submitted_by == request.user:
            return True
        
        # Assigned user has access
        if obj.assigned_to == request.user:
            return True
        
        # For other user types, check if they have a relationship to the disputed object
        if request.user.user_type == 'Artist':
            # Artists can access disputes related to their tracks
            if obj.related_track and hasattr(obj.related_track, 'artist'):
                if obj.related_track.artist.user == request.user:
                    return True
        
        elif request.user.user_type == 'Publisher':
            # Publishers can access disputes related to their artists' tracks
            if obj.related_track and hasattr(obj.related_track, 'artist'):
                # Check if publisher has relationship with the artist
                from publishers.models import PublisherArtistRelationship
                if PublisherArtistRelationship.objects.filter(
                    publisher__user=request.user,
                    artist=obj.related_track.artist,
                    status='active'
                ).exists():
                    return True
        
        elif request.user.user_type == 'Station':
            # Stations can access disputes related to their detections
            if obj.related_station:
                if hasattr(obj.related_station, 'user') and obj.related_station.user == request.user:
                    return True
        
        return False