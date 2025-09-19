from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Dispute, DisputeNotification, DisputeStatus
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Dispute)
def handle_dispute_creation(sender, instance, created, **kwargs):
    """
    Handle actions when a dispute is created
    """
    if created:
        # Notify admins about new dispute
        admin_users = User.objects.filter(user_type='Admin', is_active=True)
        
        for admin in admin_users:
            DisputeNotification.objects.create(
                dispute=instance,
                recipient=admin,
                notification_type='new_dispute',
                title=f'New Dispute Submitted: {instance.title}',
                message=f'A new dispute has been submitted by {instance.submitted_by.username}. '
                       f'Type: {instance.get_dispute_type_display()}, Priority: {instance.get_priority_display()}'
            )
        
        logger.info(f"New dispute {instance.dispute_id} created, admins notified")


@receiver(pre_save, sender=Dispute)
def handle_dispute_status_change(sender, instance, **kwargs):
    """
    Handle status changes and send appropriate notifications
    """
    if instance.pk:  # Only for existing disputes
        try:
            old_instance = Dispute.objects.get(pk=instance.pk)
            
            # Check if status changed
            if old_instance.status != instance.status:
                # Handle specific status transitions
                if instance.status == DisputeStatus.RESOLVED:
                    _handle_dispute_resolution(instance, old_instance)
                elif instance.status == DisputeStatus.ESCALATED:
                    _handle_dispute_escalation(instance, old_instance)
                elif instance.status == DisputeStatus.EVIDENCE_REQUIRED:
                    _handle_evidence_required(instance, old_instance)
        
        except Dispute.DoesNotExist:
            pass  # New dispute, handled by post_save


def _handle_dispute_resolution(instance, old_instance):
    """
    Handle dispute resolution notifications
    """
    # Notify submitter
    DisputeNotification.objects.create(
        dispute=instance,
        recipient=instance.submitted_by,
        notification_type='dispute_resolved',
        title=f'Dispute Resolved: {instance.title}',
        message=f'Your dispute has been resolved. Resolution: {instance.resolution_summary}'
    )
    
    # Notify assigned user if different from submitter
    if instance.assigned_to and instance.assigned_to != instance.submitted_by:
        DisputeNotification.objects.create(
            dispute=instance,
            recipient=instance.assigned_to,
            notification_type='dispute_resolved',
            title=f'Assigned Dispute Resolved: {instance.title}',
            message=f'The dispute you were handling has been resolved.'
        )
    
    logger.info(f"Dispute {instance.dispute_id} resolved, parties notified")


def _handle_dispute_escalation(instance, old_instance):
    """
    Handle dispute escalation notifications
    """
    # Notify all admins about escalation
    admin_users = User.objects.filter(user_type='Admin', is_active=True)
    
    for admin in admin_users:
        DisputeNotification.objects.create(
            dispute=instance,
            recipient=admin,
            notification_type='dispute_escalated',
            title=f'Dispute Escalated: {instance.title}',
            message=f'Dispute has been escalated and requires admin attention. '
                   f'Original submitter: {instance.submitted_by.username}'
        )
    
    # Notify submitter about escalation
    DisputeNotification.objects.create(
        dispute=instance,
        recipient=instance.submitted_by,
        notification_type='dispute_escalated',
        title=f'Dispute Escalated: {instance.title}',
        message=f'Your dispute has been escalated to admin level for further review.'
    )
    
    logger.info(f"Dispute {instance.dispute_id} escalated, admins and submitter notified")


def _handle_evidence_required(instance, old_instance):
    """
    Handle evidence required notifications
    """
    # Notify submitter that evidence is required
    DisputeNotification.objects.create(
        dispute=instance,
        recipient=instance.submitted_by,
        notification_type='evidence_required',
        title=f'Evidence Required: {instance.title}',
        message=f'Additional evidence is required for your dispute. '
               f'Please provide the requested documentation to proceed.'
    )
    
    logger.info(f"Evidence required for dispute {instance.dispute_id}, submitter notified")


@receiver(post_save, sender=Dispute)
def handle_dispute_assignment(sender, instance, created, **kwargs):
    """
    Handle dispute assignment notifications
    """
    if not created and instance.assigned_to:
        # Check if assignment changed
        try:
            # Get the previous version from the database
            if hasattr(instance, '_state') and instance._state.adding is False:
                # This is an update, check if assigned_to changed
                old_instance = Dispute.objects.get(pk=instance.pk)
                
                # We need to track assignment changes differently since we can't easily
                # compare with the old instance in post_save. This would be better
                # handled in the workflow class where we have explicit assignment methods.
                pass
        except Dispute.DoesNotExist:
            pass


# Auto-escalation for old unresolved disputes
def auto_escalate_old_disputes():
    """
    Celery task to auto-escalate disputes that have been open too long
    This would be called by a periodic task
    """
    from datetime import timedelta
    
    # Find disputes older than 30 days that are still in review
    cutoff_date = timezone.now() - timedelta(days=30)
    
    old_disputes = Dispute.objects.filter(
        status__in=[DisputeStatus.UNDER_REVIEW, DisputeStatus.EVIDENCE_REQUIRED],
        created_at__lt=cutoff_date
    )
    
    for dispute in old_disputes:
        # Auto-escalate
        dispute.status = DisputeStatus.ESCALATED
        dispute.save()
        
        # Create audit log
        from .workflow import DisputeWorkflow
        workflow = DisputeWorkflow()
        workflow._create_audit_log(
            dispute=dispute,
            actor=None,  # System action
            action='auto_escalated',
            description='Automatically escalated due to extended resolution time',
            previous_state=DisputeStatus.UNDER_REVIEW,
            new_state=DisputeStatus.ESCALATED
        )
        
        logger.info(f"Auto-escalated dispute {dispute.dispute_id} due to age")
    
    return len(old_disputes)