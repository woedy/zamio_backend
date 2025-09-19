from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta
import logging

from .models import (
    Dispute, DisputeEvidence, DisputeComment, DisputeNotification,
    DisputeStatus, DisputeType, DisputePriority
)
from .serializers import (
    DisputeListSerializer, DisputeDetailSerializer, DisputeCreateSerializer,
    DisputeUpdateSerializer, DisputeStatusTransitionSerializer,
    DisputeEvidenceSerializer, DisputeEvidenceCreateSerializer,
    DisputeCommentSerializer, DisputeCommentCreateSerializer,
    DisputeNotificationSerializer, DisputeStatsSerializer,
    DisputeChoicesSerializer
)
from .workflow import DisputeWorkflow
from accounts.permissions import IsAdminOrMediator, IsOwnerOrAdmin

logger = logging.getLogger(__name__)


class DisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing disputes with comprehensive CRUD operations
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Dispute.objects.select_related(
            'submitted_by', 'assigned_to', 'related_track', 'related_station'
        ).prefetch_related('evidence', 'comments', 'audit_logs')
        
        # Filter based on user role and permissions
        if user.user_type == 'Admin':
            # Admins can see all disputes
            pass
        elif user.user_type == 'Mediator':
            # Mediators can see assigned disputes and unassigned ones
            queryset = queryset.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True)
            )
        else:
            # Regular users can only see their own disputes
            queryset = queryset.filter(submitted_by=user)
        
        # Apply filters from query parameters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(dispute_type=type_filter)
        
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        assigned_filter = self.request.query_params.get('assigned_to')
        if assigned_filter:
            queryset = queryset.filter(assigned_to__user_id=assigned_filter)
        
        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(dispute_id__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DisputeListSerializer
        elif self.action == 'create':
            return DisputeCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DisputeUpdateSerializer
        else:
            return DisputeDetailSerializer
    
    def perform_create(self, serializer):
        """Create dispute with audit logging"""
        dispute = serializer.save()
        
        # Create initial audit log
        workflow = DisputeWorkflow()
        workflow._create_audit_log(
            dispute=dispute,
            actor=self.request.user,
            action='dispute_created',
            description=f'Dispute created: {dispute.title}',
            new_state=dispute.status,
            request_meta=self._get_request_meta()
        )
        
        logger.info(f"Dispute {dispute.dispute_id} created by {self.request.user.username}")
    
    def perform_update(self, serializer):
        """Update dispute with audit logging"""
        old_instance = self.get_object()
        dispute = serializer.save()
        
        # Log the update
        workflow = DisputeWorkflow()
        workflow._create_audit_log(
            dispute=dispute,
            actor=self.request.user,
            action='dispute_updated',
            description='Dispute details updated',
            request_meta=self._get_request_meta()
        )
    
    @action(detail=True, methods=['post'])
    def transition_status(self, request, pk=None):
        """
        Transition dispute to a new status
        """
        dispute = self.get_object()
        serializer = DisputeStatusTransitionSerializer(
            data=request.data,
            context={'dispute': dispute, 'user': request.user}
        )
        
        if serializer.is_valid():
            workflow = DisputeWorkflow()
            
            try:
                updated_dispute = workflow.transition_state(
                    dispute=dispute,
                    new_status=serializer.validated_data['new_status'],
                    actor=request.user,
                    reason=serializer.validated_data.get('reason', ''),
                    notify=serializer.validated_data.get('notify', True),
                    request_meta=self._get_request_meta()
                )
                
                return Response(
                    DisputeDetailSerializer(updated_dispute, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign dispute to a user
        """
        dispute = self.get_object()
        
        # Check permissions
        if request.user.user_type not in ['Admin', 'Mediator']:
            return Response(
                {'error': 'Only admins and mediators can assign disputes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        assignee_id = request.data.get('assignee_id')
        reason = request.data.get('reason', '')
        
        if not assignee_id:
            return Response(
                {'error': 'assignee_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            assignee = User.objects.get(user_id=assignee_id)
            
            if assignee.user_type not in ['Admin', 'Mediator']:
                return Response(
                    {'error': 'Can only assign to Admin or Mediator users'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            workflow = DisputeWorkflow()
            updated_dispute = workflow.assign_dispute(
                dispute=dispute,
                assignee=assignee,
                actor=request.user,
                reason=reason
            )
            
            return Response(
                DisputeDetailSerializer(updated_dispute, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def add_evidence(self, request, pk=None):
        """
        Add evidence to a dispute
        """
        dispute = self.get_object()
        
        # Check if user can add evidence
        if not (request.user == dispute.submitted_by or 
                request.user == dispute.assigned_to or 
                request.user.user_type in ['Admin', 'Mediator']):
            return Response(
                {'error': 'You do not have permission to add evidence to this dispute'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DisputeEvidenceCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            workflow = DisputeWorkflow()
            evidence = workflow.add_evidence(
                dispute=dispute,
                actor=request.user,
                title=serializer.validated_data['title'],
                description=serializer.validated_data.get('description', ''),
                file=serializer.validated_data.get('file'),
                text_content=serializer.validated_data.get('text_content', ''),
                external_url=serializer.validated_data.get('external_url', '')
            )
            
            return Response(
                DisputeEvidenceSerializer(evidence, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """
        Add comment to a dispute
        """
        dispute = self.get_object()
        
        # Check if user can add comments
        if not (request.user == dispute.submitted_by or 
                request.user == dispute.assigned_to or 
                request.user.user_type in ['Admin', 'Mediator']):
            return Response(
                {'error': 'You do not have permission to comment on this dispute'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DisputeCommentCreateSerializer(
            data=request.data,
            context={'dispute': dispute}
        )
        
        if serializer.is_valid():
            comment = serializer.save(
                dispute=dispute,
                author=request.user
            )
            
            # Create audit log
            workflow = DisputeWorkflow()
            workflow._create_audit_log(
                dispute=dispute,
                actor=request.user,
                action='comment_added',
                description=f'Comment added: {comment.content[:50]}...',
                evidence={'comment_id': comment.id}
            )
            
            return Response(
                DisputeCommentSerializer(comment, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """
        Get dispute timeline with all events
        """
        dispute = self.get_object()
        workflow = DisputeWorkflow()
        timeline = workflow.get_dispute_timeline(dispute)
        
        return Response({'timeline': timeline}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get dispute statistics for dashboard
        """
        user = request.user
        queryset = self.get_queryset()
        
        # Basic counts
        total_disputes = queryset.count()
        open_disputes = queryset.exclude(
            status__in=[DisputeStatus.RESOLVED, DisputeStatus.REJECTED]
        ).count()
        resolved_disputes = queryset.filter(status=DisputeStatus.RESOLVED).count()
        
        # Group by status
        by_status = dict(
            queryset.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        # Group by type
        by_type = dict(
            queryset.values('dispute_type').annotate(count=Count('id')).values_list('dispute_type', 'count')
        )
        
        # Group by priority
        by_priority = dict(
            queryset.values('priority').annotate(count=Count('id')).values_list('priority', 'count')
        )
        
        # Average resolution time
        resolved_queryset = queryset.filter(
            status=DisputeStatus.RESOLVED,
            resolved_at__isnull=False
        )
        
        avg_resolution_time = 0
        if resolved_queryset.exists():
            # Calculate average in days
            resolution_times = []
            for dispute in resolved_queryset:
                delta = dispute.resolved_at - dispute.created_at
                resolution_times.append(delta.total_seconds() / 86400)  # Convert to days
            
            avg_resolution_time = sum(resolution_times) / len(resolution_times)
        
        # Recent activity (last 7 days)
        recent_date = timezone.now() - timedelta(days=7)
        recent_activity = list(
            queryset.filter(created_at__gte=recent_date)
            .values('created_at__date')
            .annotate(count=Count('id'))
            .order_by('created_at__date')
        )
        
        stats_data = {
            'total_disputes': total_disputes,
            'open_disputes': open_disputes,
            'resolved_disputes': resolved_disputes,
            'by_status': by_status,
            'by_type': by_type,
            'by_priority': by_priority,
            'average_resolution_time': round(avg_resolution_time, 2),
            'recent_activity': recent_activity
        }
        
        serializer = DisputeStatsSerializer(stats_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def choices(self, request):
        """
        Get choice options for dispute forms
        """
        serializer = DisputeChoicesSerializer({})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def _get_request_meta(self):
        """Extract request metadata for audit logging"""
        return {
            'ip_address': self.request.META.get('REMOTE_ADDR'),
            'user_agent': self.request.META.get('HTTP_USER_AGENT', '')
        }


class DisputeNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for dispute notifications
    """
    serializer_class = DisputeNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DisputeNotification.objects.filter(
            recipient=self.request.user
        ).select_related('dispute').order_by('-sent_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark notification as read
        """
        notification = self.get_object()
        notification.mark_as_read()
        
        return Response(
            DisputeNotificationSerializer(notification).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read
        """
        notifications = self.get_queryset().filter(read_at__isnull=True)
        
        for notification in notifications:
            notification.mark_as_read()
        
        return Response(
            {'message': f'Marked {notifications.count()} notifications as read'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """
        Get count of unread notifications
        """
        count = self.get_queryset().filter(read_at__isnull=True).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)