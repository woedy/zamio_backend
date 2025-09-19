from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from accounts.permissions import (
    require_permission, 
    require_role, 
    require_kyc_verified,
    IsAdminUser,
    IsArtistUser,
    IsPublisherUser,
    IsKYCVerified
)
from accounts.models import UserPermission, AuditLog

User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role(['Artist'])
def artist_only_view(request):
    """Example view that only artists can access"""
    return Response({
        'message': 'This is an artist-only endpoint',
        'user': request.user.email,
        'user_type': request.user.user_type
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role(['Publisher'])
def publisher_only_view(request):
    """Example view that only publishers can access"""
    return Response({
        'message': 'This is a publisher-only endpoint',
        'user': request.user.email,
        'user_type': request.user.user_type
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role(['Admin'])
def admin_only_view(request):
    """Example view that only admins can access"""
    return Response({
        'message': 'This is an admin-only endpoint',
        'user': request.user.email,
        'user_type': request.user.user_type
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_permission('upload_music')
def upload_music_view(request):
    """Example view that requires specific permission"""
    return Response({
        'message': 'Music upload endpoint - permission verified',
        'user': request.user.email,
        'has_permission': True
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_kyc_verified
def kyc_required_view(request):
    """Example view that requires KYC verification"""
    return Response({
        'message': 'KYC-verified endpoint accessed successfully',
        'user': request.user.email,
        'kyc_status': request.user.kyc_status
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_permissions_view(request):
    """View to get current user's permissions"""
    permissions = UserPermission.objects.filter(
        user=request.user,
        is_active=True
    ).values_list('permission', flat=True)
    
    return Response({
        'user': request.user.email,
        'user_type': request.user.user_type,
        'permissions': list(permissions),
        'kyc_status': request.user.kyc_status,
        'profile_complete': request.user.profile_complete
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def grant_permission_view(request):
    """Admin endpoint to grant permissions to users"""
    user_email = request.data.get('user_email')
    permission = request.data.get('permission')
    
    if not user_email or not permission:
        return Response({
            'error': 'user_email and permission are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if permission already exists
    existing_permission = UserPermission.objects.filter(
        user=target_user,
        permission=permission
    ).first()
    
    if existing_permission:
        existing_permission.is_active = True
        existing_permission.granted_by = request.user
        existing_permission.save()
        action = 'reactivated'
    else:
        UserPermission.objects.create(
            user=target_user,
            permission=permission,
            granted_by=request.user
        )
        action = 'granted'
    
    return Response({
        'message': f'Permission {permission} {action} for user {user_email}',
        'user_email': user_email,
        'permission': permission,
        'granted_by': request.user.email
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def revoke_permission_view(request):
    """Admin endpoint to revoke permissions from users"""
    user_email = request.data.get('user_email')
    permission = request.data.get('permission')
    
    if not user_email or not permission:
        return Response({
            'error': 'user_email and permission are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Find and deactivate the permission
    user_permission = UserPermission.objects.filter(
        user=target_user,
        permission=permission,
        is_active=True
    ).first()
    
    if not user_permission:
        return Response({
            'error': 'Permission not found or already inactive'
        }, status=status.HTTP_404_NOT_FOUND)
    
    user_permission.is_active = False
    user_permission.save()
    
    return Response({
        'message': f'Permission {permission} revoked from user {user_email}',
        'user_email': user_email,
        'permission': permission,
        'revoked_by': request.user.email
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def audit_logs_view(request):
    """Admin endpoint to view audit logs"""
    # Get query parameters
    user_email = request.query_params.get('user_email')
    action = request.query_params.get('action')
    limit = int(request.query_params.get('limit', 50))
    
    # Build query
    logs = AuditLog.objects.all().order_by('-timestamp')
    
    if user_email:
        try:
            user = User.objects.get(email=user_email)
            logs = logs.filter(user=user)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    if action:
        logs = logs.filter(action__icontains=action)
    
    # Limit results
    logs = logs[:limit]
    
    # Serialize logs
    log_data = []
    for log in logs:
        log_data.append({
            'id': log.id,
            'user': log.user.email if log.user else 'System',
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'ip_address': log.ip_address,
            'status_code': log.status_code,
            'timestamp': log.timestamp,
            'trace_id': str(log.trace_id) if log.trace_id else None
        })
    
    return Response({
        'logs': log_data,
        'total_count': logs.count(),
        'filters': {
            'user_email': user_email,
            'action': action,
            'limit': limit
        }
    })