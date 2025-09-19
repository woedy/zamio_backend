from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from typing import Dict, List, Optional, Any
import logging

from .models import (
    Dispute, DisputeStatus, DisputeAuditLog, DisputeNotification,
    DisputeWorkflowRule, DisputeEvidence
)

User = get_user_model()
logger = logging.getLogger(__name__)


class DisputeWorkflowError(Exception):
    """Custom exception for dispute workflow errors"""
    pass


class InvalidTransitionError(DisputeWorkflowError):
    """Raised when an invalid state transition is attempted"""
    pass


class DisputeWorkflow:
    """
    Comprehensive dispute workflow engine with state transition management
    """
    
    # Define valid state transitions
    STATE_TRANSITIONS = {
        DisputeStatus.SUBMITTED: [
            DisputeStatus.UNDER_REVIEW,
            DisputeStatus.REJECTED
        ],
        DisputeStatus.UNDER_REVIEW: [
            DisputeStatus.EVIDENCE_REQUIRED,
            DisputeStatus.MEDIATION,
            DisputeStatus.RESOLVED,
            DisputeStatus.REJECTED
        ],
        DisputeStatus.EVIDENCE_REQUIRED: [
            DisputeStatus.UNDER_REVIEW,
            DisputeStatus.REJECTED
        ],
        DisputeStatus.MEDIATION: [
            DisputeStatus.RESOLVED,
            DisputeStatus.ESCALATED
        ],
        DisputeStatus.ESCALATED: [
            DisputeStatus.RESOLVED,
            DisputeStatus.EXTERNAL_ARBITRATION
        ],
        DisputeStatus.EXTERNAL_ARBITRATION: [
            DisputeStatus.RESOLVED
        ],
        DisputeStatus.RESOLVED: [],  # Terminal state
        DisputeStatus.REJECTED: []   # Terminal state
    }
    
    # Required roles for specific transitions
    ROLE_REQUIREMENTS = {
        (DisputeStatus.SUBMITTED, DisputeStatus.UNDER_REVIEW): ['admin', 'mediator'],
        (DisputeStatus.UNDER_REVIEW, DisputeStatus.MEDIATION): ['admin', 'mediator'],
        (DisputeStatus.MEDIATION, DisputeStatus.ESCALATED): ['admin'],
        (DisputeStatus.ESCALATED, DisputeStatus.EXTERNAL_ARBITRATION): ['admin'],
        (DisputeStatus.EXTERNAL_ARBITRATION, DisputeStatus.RESOLVED): ['admin'],
    }
    
    def __init__(self):
        self.logger = logger
    
    def can_transition(self, dispute: Dispute, new_status: str, actor: User) -> bool:
        """
        Check if a state transition is valid
        """
        try:
            self._validate_transition(dispute, new_status, actor)
            return True
        except (InvalidTransitionError, ValidationError):
            return False
    
    def transition_state(
        self,
        dispute: Dispute,
        new_status: str,
        actor: User,
        reason: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        notify: bool = True,
        request_meta: Optional[Dict[str, str]] = None
    ) -> Dispute:
        """
        Transition dispute to a new state with full audit logging
        """
        self._validate_transition(dispute, new_status, actor)
        
        previous_status = dispute.status
        
        # Update dispute status
        dispute.status = new_status
        dispute.updated_at = timezone.now()
        
        # Set resolved timestamp if transitioning to resolved
        if new_status == DisputeStatus.RESOLVED and not dispute.resolved_at:
            dispute.resolved_at = timezone.now()
        
        dispute.save()
        
        # Create audit log entry
        self._create_audit_log(
            dispute=dispute,
            actor=actor,
            action=f"state_change_{new_status}",
            description=reason or f"Status changed from {previous_status} to {new_status}",
            previous_state=previous_status,
            new_state=new_status,
            evidence=evidence or {},
            request_meta=request_meta
        )
        
        # Send notifications if enabled
        if notify:
            self._send_transition_notifications(dispute, previous_status, new_status, actor)
        
        # Execute any post-transition actions
        self._execute_post_transition_actions(dispute, previous_status, new_status, actor)
        
        self.logger.info(
            f"Dispute {dispute.dispute_id} transitioned from {previous_status} to {new_status} by {actor.username}"
        )
        
        return dispute
    
    def add_evidence(
        self,
        dispute: Dispute,
        actor: User,
        title: str,
        description: str = "",
        file=None,
        text_content: str = "",
        external_url: str = "",
        notify: bool = True
    ) -> DisputeEvidence:
        """
        Add evidence to a dispute with audit logging
        """
        evidence = DisputeEvidence.objects.create(
            dispute=dispute,
            uploaded_by=actor,
            title=title,
            description=description,
            file=file,
            text_content=text_content,
            external_url=external_url
        )
        
        # Create audit log
        self._create_audit_log(
            dispute=dispute,
            actor=actor,
            action="evidence_added",
            description=f"Evidence added: {title}",
            evidence={
                'evidence_id': str(evidence.id),
                'title': title,
                'has_file': bool(file),
                'has_text': bool(text_content),
                'has_url': bool(external_url)
            }
        )
        
        # Send notifications
        if notify:
            self._send_evidence_notifications(dispute, evidence, actor)
        
        return evidence
    
    def assign_dispute(
        self,
        dispute: Dispute,
        assignee: User,
        actor: User,
        reason: str = "",
        notify: bool = True
    ) -> Dispute:
        """
        Assign dispute to a user with audit logging
        """
        previous_assignee = dispute.assigned_to
        dispute.assigned_to = assignee
        dispute.save()
        
        # Create audit log
        self._create_audit_log(
            dispute=dispute,
            actor=actor,
            action="dispute_assigned",
            description=reason or f"Dispute assigned to {assignee.username}",
            evidence={
                'previous_assignee': previous_assignee.username if previous_assignee else None,
                'new_assignee': assignee.username
            }
        )
        
        # Send notifications
        if notify:
            self._send_assignment_notifications(dispute, assignee, actor)
        
        return dispute
    
    def get_available_transitions(self, dispute: Dispute, actor: User) -> List[str]:
        """
        Get list of valid transitions for current user and dispute state
        """
        available = []
        current_status = dispute.status
        
        if current_status in self.STATE_TRANSITIONS:
            for next_status in self.STATE_TRANSITIONS[current_status]:
                if self.can_transition(dispute, next_status, actor):
                    available.append(next_status)
        
        return available
    
    def get_dispute_timeline(self, dispute: Dispute) -> List[Dict[str, Any]]:
        """
        Get chronological timeline of dispute events
        """
        timeline = []
        
        # Get audit logs
        audit_logs = dispute.audit_logs.all().order_by('timestamp')
        
        for log in audit_logs:
            timeline.append({
                'type': 'audit_log',
                'timestamp': log.timestamp,
                'actor': log.actor.username,
                'action': log.action,
                'description': log.description,
                'previous_state': log.previous_state,
                'new_state': log.new_state,
                'evidence': log.evidence
            })
        
        # Get comments
        comments = dispute.comments.all().order_by('created_at')
        
        for comment in comments:
            timeline.append({
                'type': 'comment',
                'timestamp': comment.created_at,
                'actor': comment.author.username,
                'action': 'comment_added',
                'description': comment.content,
                'is_internal': comment.is_internal
            })
        
        # Get evidence
        evidence_items = dispute.evidence.all().order_by('uploaded_at')
        
        for evidence in evidence_items:
            timeline.append({
                'type': 'evidence',
                'timestamp': evidence.uploaded_at,
                'actor': evidence.uploaded_by.username,
                'action': 'evidence_added',
                'description': f"Evidence: {evidence.title}",
                'evidence_id': evidence.id
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def _validate_transition(self, dispute: Dispute, new_status: str, actor: User):
        """
        Validate if a state transition is allowed
        """
        current_status = dispute.status
        
        # Check if transition is valid
        if current_status not in self.STATE_TRANSITIONS:
            raise InvalidTransitionError(f"Invalid current status: {current_status}")
        
        if new_status not in self.STATE_TRANSITIONS[current_status]:
            raise InvalidTransitionError(
                f"Cannot transition from {current_status} to {new_status}"
            )
        
        # Check role requirements
        transition_key = (current_status, new_status)
        if transition_key in self.ROLE_REQUIREMENTS:
            required_roles = self.ROLE_REQUIREMENTS[transition_key]
            user_type = getattr(actor, 'user_type', '').lower()
            
            if user_type not in required_roles:
                raise ValidationError(
                    f"User role '{user_type}' not authorized for this transition. "
                    f"Required roles: {required_roles}"
                )
        
        # Check workflow rules
        workflow_rules = DisputeWorkflowRule.objects.filter(
            from_status=current_status,
            to_status=new_status,
            is_active=True
        )
        
        for rule in workflow_rules:
            if rule.required_role and getattr(actor, 'user_type', '').lower() != rule.required_role:
                raise ValidationError(f"Required role: {rule.required_role}")
            
            if rule.requires_evidence and not dispute.evidence.exists():
                raise ValidationError("Evidence is required for this transition")
    
    def _create_audit_log(
        self,
        dispute: Dispute,
        actor: User,
        action: str,
        description: str,
        previous_state: str = "",
        new_state: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        request_meta: Optional[Dict[str, str]] = None
    ):
        """
        Create comprehensive audit log entry
        """
        DisputeAuditLog.objects.create(
            dispute=dispute,
            actor=actor,
            action=action,
            description=description,
            previous_state=previous_state,
            new_state=new_state,
            evidence=evidence or {},
            ip_address=request_meta.get('ip_address') if request_meta else None,
            user_agent=request_meta.get('user_agent') if request_meta else None
        )
    
    def _send_transition_notifications(
        self,
        dispute: Dispute,
        previous_status: str,
        new_status: str,
        actor: User
    ):
        """
        Send notifications for state transitions
        """
        # Notify dispute submitter
        if dispute.submitted_by != actor:
            DisputeNotification.objects.create(
                dispute=dispute,
                recipient=dispute.submitted_by,
                notification_type='status_change',
                title=f'Dispute Status Updated: {dispute.title}',
                message=f'Your dispute status has been changed from {previous_status} to {new_status} by {actor.username}.'
            )
        
        # Notify assigned user
        if dispute.assigned_to and dispute.assigned_to != actor:
            DisputeNotification.objects.create(
                dispute=dispute,
                recipient=dispute.assigned_to,
                notification_type='status_change',
                title=f'Assigned Dispute Status Updated: {dispute.title}',
                message=f'Dispute status has been changed from {previous_status} to {new_status} by {actor.username}.'
            )
    
    def _send_evidence_notifications(
        self,
        dispute: Dispute,
        evidence: DisputeEvidence,
        actor: User
    ):
        """
        Send notifications when evidence is added
        """
        # Notify relevant parties
        recipients = []
        
        if dispute.submitted_by != actor:
            recipients.append(dispute.submitted_by)
        
        if dispute.assigned_to and dispute.assigned_to != actor:
            recipients.append(dispute.assigned_to)
        
        for recipient in recipients:
            DisputeNotification.objects.create(
                dispute=dispute,
                recipient=recipient,
                notification_type='evidence_added',
                title=f'New Evidence Added: {dispute.title}',
                message=f'New evidence "{evidence.title}" has been added to the dispute by {actor.username}.'
            )
    
    def _send_assignment_notifications(
        self,
        dispute: Dispute,
        assignee: User,
        actor: User
    ):
        """
        Send notifications when dispute is assigned
        """
        # Notify assignee
        if assignee != actor:
            DisputeNotification.objects.create(
                dispute=dispute,
                recipient=assignee,
                notification_type='dispute_assigned',
                title=f'Dispute Assigned: {dispute.title}',
                message=f'You have been assigned to handle this dispute by {actor.username}.'
            )
        
        # Notify submitter
        if dispute.submitted_by != actor and dispute.submitted_by != assignee:
            DisputeNotification.objects.create(
                dispute=dispute,
                recipient=dispute.submitted_by,
                notification_type='dispute_assigned',
                title=f'Dispute Assignment Update: {dispute.title}',
                message=f'Your dispute has been assigned to {assignee.username} for resolution.'
            )
    
    def _execute_post_transition_actions(
        self,
        dispute: Dispute,
        previous_status: str,
        new_status: str,
        actor: User
    ):
        """
        Execute any automated actions after state transitions
        """
        # Auto-assign to admin for escalated disputes
        if new_status == DisputeStatus.ESCALATED and not dispute.assigned_to:
            # Find available admin user
            admin_users = User.objects.filter(user_type='Admin', is_active=True)
            if admin_users.exists():
                dispute.assigned_to = admin_users.first()
                dispute.save()
        
        # Set priority to urgent for external arbitration
        if new_status == DisputeStatus.EXTERNAL_ARBITRATION:
            dispute.priority = 'urgent'
            dispute.save()
        
        # Additional automated actions can be added here
        pass