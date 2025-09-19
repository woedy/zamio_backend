"""
Enhanced User and Account Management Views for Admin Dashboard
Implements comprehensive user oversight, KYC management, and bulk operations
"""

from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
import csv
import json
from datetime import datetime, timedelta

from accounts.models import AuditLog, UserPermission
from artists.models import Artist
from publishers.models import PublisherProfile
from stations.models import Station
from mr_admin.models import MrAdmin

User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_user_management_overview(request):
    """Get overview statistics for user management dashboard"""
    payload = {}
    data = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # User statistics by type
        user_stats = {
            'total_users': User.objects.filter(is_active=True).count(),
            'artists': User.objects.filter(user_type='Artist', is_active=True).count(),
            'publishers': User.objects.filter(user_type='Publisher', is_active=True).count(),
            'stations': User.objects.filter(user_type='Station', is_active=True).count(),
            'admins': User.objects.filter(user_type='Admin', is_active=True).count(),
        }
        
        # KYC statistics
        kyc_stats = {
            'pending': User.objects.filter(kyc_status='pending').count(),
            'verified': User.objects.filter(kyc_status='verified').count(),
            'rejected': User.objects.filter(kyc_status='rejected').count(),
            'incomplete': User.objects.filter(kyc_status='incomplete').count(),
        }
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_stats = {
            'new_registrations': User.objects.filter(timestamp__gte=thirty_days_ago).count(),
            'kyc_submissions': User.objects.filter(
                kyc_status__in=['pending', 'verified'], 
                timestamp__gte=thirty_days_ago
            ).count(),
            'active_users': User.objects.filter(
                last_activity__gte=thirty_days_ago,
                is_active=True
            ).count(),
        }
        
        # Account status distribution
        account_stats = {
            'active': User.objects.filter(is_active=True).count(),
            'inactive': User.objects.filter(is_active=False).count(),
            'email_verified': User.objects.filter(email_verified=True).count(),
            'profile_complete': User.objects.filter(profile_complete=True).count(),
        }
        
        data = {
            'user_stats': user_stats,
            'kyc_stats': kyc_stats,
            'recent_stats': recent_stats,
            'account_stats': account_stats,
            'last_updated': timezone.now().isoformat()
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        # Log admin action
        AuditLog.objects.create(
            user=request.user,
            action='view_user_management_overview',
            resource_type='user_management',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_users(request):
    """Get paginated list of all users with filtering and search"""
    payload = {}
    data = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        search = request.GET.get('search', '').strip()
        user_type = request.GET.get('user_type', '')
        kyc_status = request.GET.get('kyc_status', '')
        account_status = request.GET.get('account_status', '')
        order_by = request.GET.get('order_by', '-timestamp')
        
        # Build queryset
        queryset = User.objects.all()
        
        # Apply filters
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone__icontains=search)
            )
        
        if user_type:
            queryset = queryset.filter(user_type=user_type)
            
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
            
        if account_status == 'active':
            queryset = queryset.filter(is_active=True)
        elif account_status == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif account_status == 'email_verified':
            queryset = queryset.filter(email_verified=True)
        elif account_status == 'profile_incomplete':
            queryset = queryset.filter(profile_complete=False)
        
        # Apply ordering
        valid_order_fields = ['timestamp', '-timestamp', 'email', '-email', 'last_activity', '-last_activity']
        if order_by in valid_order_fields:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-timestamp')
        
        # Paginate
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        # Serialize users
        users_data = []
        for user in page_obj:
            user_data = {
                'user_id': str(user.user_id) if user.user_id else None,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'country': user.country,
                'user_type': user.user_type,
                'kyc_status': user.kyc_status,
                'is_active': user.is_active,
                'email_verified': user.email_verified,
                'profile_complete': user.profile_complete,
                'two_factor_enabled': user.two_factor_enabled,
                'last_activity': user.last_activity.isoformat() if user.last_activity else None,
                'timestamp': user.timestamp.isoformat(),
                'photo_url': user.photo.url if user.photo else None,
            }
            
            # Add type-specific data
            if user.user_type == 'Artist':
                try:
                    artist = Artist.objects.get(user=user)
                    user_data['artist_id'] = artist.artist_id
                    user_data['stage_name'] = artist.stage_name
                    user_data['self_published'] = getattr(artist, 'self_published', True)
                except Artist.DoesNotExist:
                    pass
            elif user.user_type == 'Publisher':
                try:
                    publisher = PublisherProfile.objects.get(user=user)
                    user_data['publisher_id'] = publisher.publisher_id
                    user_data['company_name'] = publisher.company_name
                except PublisherProfile.DoesNotExist:
                    pass
            elif user.user_type == 'Station':
                try:
                    station = Station.objects.get(user=user)
                    user_data['station_id'] = station.station_id
                    user_data['station_name'] = station.name
                except Station.DoesNotExist:
                    pass
            
            users_data.append(user_data)
        
        # Pagination info
        pagination_data = {
            'page_number': page,
            'per_page': per_page,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'next': page + 1 if page_obj.has_next() else None,
            'previous': page - 1 if page_obj.has_previous() else None,
        }
        
        data = {
            'users': users_data,
            'pagination': pagination_data,
            'filters_applied': {
                'search': search,
                'user_type': user_type,
                'kyc_status': kyc_status,
                'account_status': account_status,
                'order_by': order_by
            }
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_user_details(request):
    """Get detailed information about a specific user"""
    payload = {}
    data = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_id = request.GET.get('user_id')
    if not user_id:
        return Response({
            'message': 'Error',
            'errors': {'user_id': ['User ID is required']}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(user_id=user_id)
        
        # Basic user data
        user_data = {
            'user_id': str(user.user_id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
            'country': user.country,
            'user_type': user.user_type,
            'kyc_status': user.kyc_status,
            'kyc_documents': user.kyc_documents,
            'is_active': user.is_active,
            'email_verified': user.email_verified,
            'profile_complete': user.profile_complete,
            'two_factor_enabled': user.two_factor_enabled,
            'last_activity': user.last_activity.isoformat() if user.last_activity else None,
            'timestamp': user.timestamp.isoformat(),
            'photo_url': user.photo.url if user.photo else None,
            'failed_login_attempts': user.failed_login_attempts,
            'account_locked_until': user.account_locked_until.isoformat() if user.account_locked_until else None,
        }
        
        # Get user permissions
        permissions = UserPermission.objects.filter(user=user, is_active=True)
        user_data['permissions'] = [
            {
                'permission': perm.permission,
                'granted_by': perm.granted_by.email,
                'granted_at': perm.granted_at.isoformat(),
                'expires_at': perm.expires_at.isoformat() if perm.expires_at else None
            }
            for perm in permissions
        ]
        
        # Get recent audit logs for this user
        recent_logs = AuditLog.objects.filter(user=user).order_by('-timestamp')[:10]
        user_data['recent_activity'] = [
            {
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address,
                'status_code': log.status_code
            }
            for log in recent_logs
        ]
        
        # Add type-specific detailed data
        if user.user_type == 'Artist':
            try:
                artist = Artist.objects.get(user=user)
                user_data['artist_profile'] = {
                    'artist_id': artist.artist_id,
                    'stage_name': artist.stage_name,
                    'bio': getattr(artist, 'bio', ''),
                    'self_published': getattr(artist, 'self_published', True),
                    'total_tracks': getattr(artist, 'total_tracks', 0),
                    'total_earnings': getattr(artist, 'total_earnings', 0),
                }
            except Artist.DoesNotExist:
                user_data['artist_profile'] = None
                
        elif user.user_type == 'Publisher':
            try:
                publisher = PublisherProfile.objects.get(user=user)
                user_data['publisher_profile'] = {
                    'publisher_id': publisher.publisher_id,
                    'company_name': publisher.company_name,
                    'website': getattr(publisher, 'website', ''),
                    'verified': getattr(publisher, 'verified', False),
                    'total_artists': getattr(publisher, 'total_artists', 0),
                }
            except PublisherProfile.DoesNotExist:
                user_data['publisher_profile'] = None
                
        elif user.user_type == 'Station':
            try:
                station = Station.objects.get(user=user)
                user_data['station_profile'] = {
                    'station_id': station.station_id,
                    'name': station.name,
                    'city': getattr(station, 'city', ''),
                    'region': getattr(station, 'region', ''),
                    'frequency': getattr(station, 'frequency', ''),
                    'compliance_status': getattr(station, 'compliance_status', 'pending'),
                }
            except Station.DoesNotExist:
                user_data['station_profile'] = None
        
        data = user_data
        payload['message'] = 'Successful'
        payload['data'] = data
        
        # Log admin action
        AuditLog.objects.create(
            user=request.user,
            action='view_user_details',
            resource_type='user',
            resource_id=str(user.user_id),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'message': 'Error',
            'errors': {'user': ['User not found']}
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def update_kyc_status(request):
    """Update KYC status for a user with admin approval/rejection"""
    payload = {}
    data = {}
    errors = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_id = request.data.get('user_id')
    new_status = request.data.get('kyc_status')
    rejection_reason = request.data.get('rejection_reason', '')
    admin_notes = request.data.get('admin_notes', '')
    
    if not user_id:
        errors['user_id'] = ['User ID is required']
    if not new_status:
        errors['kyc_status'] = ['KYC status is required']
    if new_status not in ['pending', 'verified', 'rejected', 'incomplete']:
        errors['kyc_status'] = ['Invalid KYC status']
    if new_status == 'rejected' and not rejection_reason:
        errors['rejection_reason'] = ['Rejection reason is required when rejecting KYC']
    
    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(user_id=user_id)
        old_status = user.kyc_status
        
        # Update KYC status
        user.kyc_status = new_status
        
        # Update KYC documents with admin decision
        if not user.kyc_documents:
            user.kyc_documents = {}
        
        user.kyc_documents.update({
            'admin_decision': {
                'status': new_status,
                'decided_by': request.user.email,
                'decided_at': timezone.now().isoformat(),
                'rejection_reason': rejection_reason if new_status == 'rejected' else '',
                'admin_notes': admin_notes,
                'previous_status': old_status
            }
        })
        
        user.save()
        
        data = {
            'user_id': str(user.user_id),
            'email': user.email,
            'old_kyc_status': old_status,
            'new_kyc_status': new_status,
            'updated_by': request.user.email,
            'updated_at': timezone.now().isoformat()
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        # Log admin action
        AuditLog.objects.create(
            user=request.user,
            action='update_kyc_status',
            resource_type='user',
            resource_id=str(user.user_id),
            request_data={
                'old_status': old_status,
                'new_status': new_status,
                'rejection_reason': rejection_reason,
                'admin_notes': admin_notes
            },
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'message': 'Error',
            'errors': {'user': ['User not found']}
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def update_user_status(request):
    """Activate, deactivate, or suspend user accounts"""
    payload = {}
    data = {}
    errors = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_id = request.data.get('user_id')
    action = request.data.get('action')  # 'activate', 'deactivate', 'suspend'
    reason = request.data.get('reason', '')
    suspension_duration = request.data.get('suspension_duration')  # hours
    
    if not user_id:
        errors['user_id'] = ['User ID is required']
    if not action:
        errors['action'] = ['Action is required']
    if action not in ['activate', 'deactivate', 'suspend']:
        errors['action'] = ['Invalid action. Must be activate, deactivate, or suspend']
    if action in ['deactivate', 'suspend'] and not reason:
        errors['reason'] = ['Reason is required for deactivation or suspension']
    
    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(user_id=user_id)
        
        # Prevent admin from deactivating themselves
        if user == request.user and action in ['deactivate', 'suspend']:
            return Response({
                'message': 'Error',
                'errors': {'action': ['Cannot deactivate or suspend your own account']}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = {
            'is_active': user.is_active,
            'account_locked_until': user.account_locked_until
        }
        
        if action == 'activate':
            user.is_active = True
            user.account_locked_until = None
            user.failed_login_attempts = 0
        elif action == 'deactivate':
            user.is_active = False
            user.account_locked_until = None
        elif action == 'suspend':
            user.is_active = False
            if suspension_duration:
                user.account_locked_until = timezone.now() + timedelta(hours=int(suspension_duration))
        
        user.save()
        
        data = {
            'user_id': str(user.user_id),
            'email': user.email,
            'action': action,
            'old_status': old_status,
            'new_status': {
                'is_active': user.is_active,
                'account_locked_until': user.account_locked_until.isoformat() if user.account_locked_until else None
            },
            'updated_by': request.user.email,
            'updated_at': timezone.now().isoformat(),
            'reason': reason
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        # Log admin action
        AuditLog.objects.create(
            user=request.user,
            action=f'user_{action}',
            resource_type='user',
            resource_id=str(user.user_id),
            request_data={
                'action': action,
                'reason': reason,
                'suspension_duration': suspension_duration,
                'old_status': old_status
            },
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'message': 'Error',
            'errors': {'user': ['User not found']}
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def bulk_user_operations(request):
    """Perform bulk operations on multiple users"""
    payload = {}
    data = {}
    errors = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_ids = request.data.get('user_ids', [])
    operation = request.data.get('operation')  # 'activate', 'deactivate', 'export', 'update_kyc'
    operation_data = request.data.get('operation_data', {})
    
    if not user_ids:
        errors['user_ids'] = ['User IDs are required']
    if not operation:
        errors['operation'] = ['Operation is required']
    if operation not in ['activate', 'deactivate', 'export', 'update_kyc']:
        errors['operation'] = ['Invalid operation']
    
    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        users = User.objects.filter(user_id__in=user_ids)
        
        if operation == 'export':
            # Export user data to CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'User ID', 'Email', 'First Name', 'Last Name', 'Phone', 'Country',
                'User Type', 'KYC Status', 'Is Active', 'Email Verified', 'Profile Complete',
                'Registration Date', 'Last Activity'
            ])
            
            for user in users:
                writer.writerow([
                    str(user.user_id),
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.phone,
                    user.country,
                    user.user_type,
                    user.kyc_status,
                    user.is_active,
                    user.email_verified,
                    user.profile_complete,
                    user.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    user.last_activity.strftime('%Y-%m-%d %H:%M:%S') if user.last_activity else ''
                ])
            
            # Log bulk export
            AuditLog.objects.create(
                user=request.user,
                action='bulk_export_users',
                resource_type='user',
                request_data={'user_count': len(users), 'user_ids': user_ids},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return response
        
        # For other operations, update users
        updated_users = []
        failed_updates = []
        
        for user in users:
            try:
                # Prevent admin from affecting their own account in bulk operations
                if user == request.user and operation in ['deactivate']:
                    failed_updates.append({
                        'user_id': str(user.user_id),
                        'email': user.email,
                        'error': 'Cannot deactivate your own account'
                    })
                    continue
                
                if operation == 'activate':
                    user.is_active = True
                    user.account_locked_until = None
                    user.failed_login_attempts = 0
                elif operation == 'deactivate':
                    user.is_active = False
                elif operation == 'update_kyc':
                    new_status = operation_data.get('kyc_status')
                    if new_status in ['pending', 'verified', 'rejected', 'incomplete']:
                        user.kyc_status = new_status
                
                user.save()
                updated_users.append({
                    'user_id': str(user.user_id),
                    'email': user.email,
                    'operation': operation
                })
                
            except Exception as e:
                failed_updates.append({
                    'user_id': str(user.user_id),
                    'email': user.email,
                    'error': str(e)
                })
        
        data = {
            'operation': operation,
            'total_requested': len(user_ids),
            'successful_updates': len(updated_users),
            'failed_updates': len(failed_updates),
            'updated_users': updated_users,
            'failed_users': failed_updates,
            'performed_by': request.user.email,
            'performed_at': timezone.now().isoformat()
        }
        
        payload['message'] = 'Completed'
        payload['data'] = data
        
        # Log bulk operation
        AuditLog.objects.create(
            user=request.user,
            action=f'bulk_{operation}',
            resource_type='user',
            request_data={
                'operation': operation,
                'user_ids': user_ids,
                'operation_data': operation_data,
                'successful_count': len(updated_users),
                'failed_count': len(failed_updates)
            },
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_kyc_pending_users(request):
    """Get list of users with pending KYC for review"""
    payload = {}
    data = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        # Get users with pending KYC that have documents
        queryset = User.objects.filter(
            kyc_status='pending'
        ).exclude(
            kyc_documents={}
        ).order_by('timestamp')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        users_data = []
        for user in page_obj:
            user_data = {
                'user_id': str(user.user_id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user_type': user.user_type,
                'kyc_documents': user.kyc_documents,
                'submitted_at': user.timestamp.isoformat(),
                'photo_url': user.photo.url if user.photo else None,
            }
            users_data.append(user_data)
        
        pagination_data = {
            'page_number': page,
            'per_page': per_page,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
        
        data = {
            'pending_kyc_users': users_data,
            'pagination': pagination_data
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_
view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_kyc_pending_users(request):
    """Get all users with pending KYC status for review"""
    payload = {}
    data = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get users with pending or incomplete KYC status
        users = User.objects.filter(
            kyc_status__in=['pending', 'incomplete']
        ).order_by('-timestamp')
        
        users_data = []
        for user in users:
            user_data = {
                'user_id': str(user.user_id) if user.user_id else None,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'country': user.country,
                'user_type': user.user_type,
                'kyc_status': user.kyc_status,
                'kyc_documents': user.kyc_documents,
                'is_active': user.is_active,
                'email_verified': user.email_verified,
                'profile_complete': user.profile_complete,
                'timestamp': user.timestamp.isoformat(),
                'photo_url': user.photo.url if user.photo else None,
            }
            
            # Add type-specific data
            if user.user_type == 'Artist':
                try:
                    artist = Artist.objects.get(user=user)
                    user_data['stage_name'] = artist.stage_name
                except Artist.DoesNotExist:
                    pass
            elif user.user_type == 'Publisher':
                try:
                    publisher = PublisherProfile.objects.get(user=user)
                    user_data['company_name'] = publisher.company_name
                except PublisherProfile.DoesNotExist:
                    pass
            elif user.user_type == 'Station':
                try:
                    station = Station.objects.get(user=user)
                    user_data['station_name'] = station.name
                except Station.DoesNotExist:
                    pass
            
            users_data.append(user_data)
        
        data = {
            'users': users_data,
            'total_count': len(users_data)
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        # Log admin action
        AuditLog.objects.create(
            user=request.user,
            action='view_kyc_pending_users',
            resource_type='user_management',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_vi
ew(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_audit_logs(request):
    """Get paginated audit logs with filtering for admin dashboard"""
    payload = {}
    data = {}
    
    # Verify admin permissions
    if not hasattr(request.user, 'mr_admin') or request.user.user_type != 'Admin':
        return Response({
            'message': 'Unauthorized',
            'errors': {'permission': ['Admin access required']}
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        search = request.GET.get('search', '').strip()
        action = request.GET.get('action', '')
        resource_type = request.GET.get('resource_type', '')
        user_type = request.GET.get('user_type', '')
        status_code = request.GET.get('status_code', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        
        # Build queryset
        queryset = AuditLog.objects.all()
        
        # Apply filters
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(resource_type__icontains=search) |
                Q(resource_id__icontains=search)
            )
        
        if action:
            queryset = queryset.filter(action__icontains=action)
            
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
            
        if user_type:
            queryset = queryset.filter(user__user_type=user_type)
            
        if status_code:
            queryset = queryset.filter(status_code=int(status_code))
            
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                start_dt = timezone.make_aware(start_dt)
                queryset = queryset.filter(timestamp__gte=start_dt)
            except ValueError:
                pass
                
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                end_dt = timezone.make_aware(end_dt)
                queryset = queryset.filter(timestamp__lt=end_dt)
            except ValueError:
                pass
        
        # Order by timestamp (newest first)
        queryset = queryset.order_by('-timestamp')
        
        # Paginate
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        # Serialize audit logs
        logs_data = []
        for log in page_obj:
            log_data = {
                'id': str(log.id),
                'user': {
                    'email': log.user.email,
                    'first_name': log.user.first_name,
                    'last_name': log.user.last_name,
                    'user_type': log.user.user_type
                } if log.user else None,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'request_data': log.request_data,
                'response_data': log.response_data,
                'status_code': log.status_code,
                'timestamp': log.timestamp.isoformat(),
                'trace_id': str(log.trace_id) if log.trace_id else None,
            }
            logs_data.append(log_data)
        
        # Pagination info
        pagination_data = {
            'page_number': page,
            'per_page': per_page,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'next': page + 1 if page_obj.has_next() else None,
            'previous': page - 1 if page_obj.has_previous() else None,
        }
        
        data = {
            'audit_logs': logs_data,
            'pagination': pagination_data,
            'filters_applied': {
                'search': search,
                'action': action,
                'resource_type': resource_type,
                'user_type': user_type,
                'status_code': status_code,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        payload['message'] = 'Successful'
        payload['data'] = data
        
        return Response(payload, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'message': 'Error',
            'errors': {'system': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)