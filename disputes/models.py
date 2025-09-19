from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class DisputeType(models.TextChoices):
    DETECTION_ACCURACY = 'detection_accuracy', 'Detection Accuracy'
    ROYALTY_CALCULATION = 'royalty_calculation', 'Royalty Calculation'
    OWNERSHIP_CLAIM = 'ownership_claim', 'Ownership Claim'
    PAYMENT_ISSUE = 'payment_issue', 'Payment Issue'
    METADATA_ERROR = 'metadata_error', 'Metadata Error'
    OTHER = 'other', 'Other'


class DisputeStatus(models.TextChoices):
    SUBMITTED = 'submitted', 'Submitted'
    UNDER_REVIEW = 'under_review', 'Under Review'
    EVIDENCE_REQUIRED = 'evidence_required', 'Evidence Required'
    MEDIATION = 'mediation', 'Mediation'
    ESCALATED = 'escalated', 'Escalated'
    RESOLVED = 'resolved', 'Resolved'
    REJECTED = 'rejected', 'Rejected'
    EXTERNAL_ARBITRATION = 'external_arbitration', 'External Arbitration'


class DisputePriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class Dispute(models.Model):
    """
    Main dispute model representing a formal dispute case
    """
    dispute_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    dispute_type = models.CharField(max_length=50, choices=DisputeType.choices)
    status = models.CharField(max_length=50, choices=DisputeStatus.choices, default=DisputeStatus.SUBMITTED)
    priority = models.CharField(max_length=20, choices=DisputePriority.choices, default=DisputePriority.MEDIUM)
    
    # Parties involved
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_disputes')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_disputes')
    
    # Related objects (optional - depends on dispute type)
    related_track = models.ForeignKey('artists.Track', on_delete=models.SET_NULL, null=True, blank=True)
    related_detection = models.ForeignKey('music_monitor.AudioDetection', on_delete=models.SET_NULL, null=True, blank=True)
    related_royalty = models.ForeignKey('music_monitor.RoyaltyDistribution', on_delete=models.SET_NULL, null=True, blank=True)
    related_station = models.ForeignKey('stations.Station', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution details
    resolution_summary = models.TextField(blank=True)
    resolution_action_taken = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['dispute_type', 'created_at']),
            models.Index(fields=['submitted_by', 'status']),
        ]
    
    def __str__(self):
        return f"Dispute {self.dispute_id}: {self.title}"
    
    def save(self, *args, **kwargs):
        if self.status == DisputeStatus.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)


class DisputeEvidence(models.Model):
    """
    Evidence and documentation attached to disputes
    """
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidence')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File attachments
    file = models.FileField(upload_to='dispute_evidence/', null=True, blank=True)
    file_type = models.CharField(max_length=50, blank=True)  # audio, image, document, etc.
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Text evidence
    text_content = models.TextField(blank=True)
    
    # External references
    external_url = models.URLField(blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Evidence: {self.title} for {self.dispute.dispute_id}"


class DisputeAuditLog(models.Model):
    """
    Comprehensive audit trail for all dispute-related actions
    """
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    
    action = models.CharField(max_length=100)  # state_change, evidence_added, comment_added, etc.
    description = models.TextField()
    
    # State transition tracking
    previous_state = models.CharField(max_length=50, blank=True)
    new_state = models.CharField(max_length=50, blank=True)
    
    # Additional context
    evidence = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['dispute', 'timestamp']),
            models.Index(fields=['actor', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Audit: {self.action} on {self.dispute.dispute_id} by {self.actor.username}"


class DisputeComment(models.Model):
    """
    Comments and communication within disputes
    """
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    
    content = models.TextField()
    is_internal = models.BooleanField(default=False)  # Internal admin notes vs public comments
    
    # Reply functionality
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.dispute.dispute_id}"


class DisputeWorkflowRule(models.Model):
    """
    Configurable workflow rules for dispute state transitions
    """
    from_status = models.CharField(max_length=50, choices=DisputeStatus.choices)
    to_status = models.CharField(max_length=50, choices=DisputeStatus.choices)
    
    # Conditions
    required_role = models.CharField(max_length=50, blank=True)  # admin, mediator, etc.
    requires_evidence = models.BooleanField(default=False)
    auto_transition = models.BooleanField(default=False)
    
    # Notifications
    notify_submitter = models.BooleanField(default=True)
    notify_assigned = models.BooleanField(default=True)
    notify_stakeholders = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['from_status', 'to_status']
    
    def __str__(self):
        return f"Rule: {self.from_status} -> {self.to_status}"


class DisputeNotification(models.Model):
    """
    Notifications related to dispute status changes and updates
    """
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    
    notification_type = models.CharField(max_length=50)  # status_change, evidence_added, comment_added, etc.
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Delivery tracking
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['recipient', 'read_at']),
            models.Index(fields=['dispute', 'sent_at']),
        ]
    
    def __str__(self):
        return f"Notification: {self.title} to {self.recipient.username}"
    
    def mark_as_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=['read_at'])