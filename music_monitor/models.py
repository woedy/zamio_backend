# models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid

from artists.models import Track
from fan.models import Fan
from stations.models import Station, StationProgram

User = get_user_model()

class MatchCache(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="match_track")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="match_station")
    station_program = models.ForeignKey(StationProgram, null=True, blank=True, on_delete=models.SET_NULL,  related_name="match_station_program")

    matched_at = models.DateTimeField(auto_now_add=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    processed = models.BooleanField(default=False)
    failed_reason = models.TextField(null=True, blank=True)  # NEW field


    


class PlayLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_playlog")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="station_playlog")
    station_program = models.ForeignKey(StationProgram, on_delete=models.CASCADE, related_name="station_program_playlog", null=True, blank=True)
    
    source = models.CharField(max_length=50, choices=[('Radio', 'Radio'), ('Streaming', 'Streaming')])

    played_at = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    claimed = models.BooleanField(default=False)

    flagged = models.BooleanField(default=False)
 
    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class FailedPlayLog(models.Model):
    match = models.ForeignKey(MatchCache, on_delete=models.CASCADE)
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    will_retry = models.BooleanField(default=True)

    def __str__(self):
        return f"FailedPlayLog for MatchCache {self.match.id} at {self.timestamp}"


STATUS_TYPE = (
 
    ('Flagged', 'Flagged'),
    ('Pending', 'Pending'),
    ('Verified', 'Verified'),
    ('Resolving', 'Resolving'),
    ('Review', 'Review'),
    ('Resolved', 'Resolved')

)

class Dispute(models.Model):
    playlog = models.ForeignKey(PlayLog, on_delete=models.CASCADE, related_name="dispute_playlog")

    dispute_status = models.CharField(max_length=100, choices=STATUS_TYPE, blank=True, null=True)
    dispute_comments = models.TextField(blank=True, null=True)
    resolve_comments = models.TextField(blank=True, null=True)


    pending_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    resolving_time = models.DateTimeField(null=True, blank=True)
    review_time = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DurationField(null=True, blank=True)


    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StreamLog(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_streamlog")
    fan = models.ForeignKey(Fan, on_delete=models.CASCADE, null=True, blank=True, related_name="fan_playlog")
    

    played_at = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avg_confidence_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    claimed = models.BooleanField(default=False)

    flagged = models.BooleanField(default=False)
    dispute_status = models.CharField(max_length=100, choices=STATUS_TYPE, blank=True, null=True)
    disput_comments = models.TextField(blank=True, null=True)

    is_archived = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AudioDetection(models.Model):
    """Enhanced audio detection model with support for local and ACRCloud sources"""
    DETECTION_SOURCES = [
        ('local', 'Local Fingerprinting'),
        ('acrcloud', 'ACRCloud External'),
        ('hybrid', 'Hybrid Detection'),
    ]
    
    PROCESSING_STATUS = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('retry', 'Retry Required'),
    ]
    
    PRO_AFFILIATIONS = [
        ('ghamro', 'GHAMRO (Ghana)'),
        ('ascap', 'ASCAP (USA)'),
        ('bmi', 'BMI (USA)'),
        ('prs', 'PRS (UK)'),
        ('sacem', 'SACEM (France)'),
        ('gema', 'GEMA (Germany)'),
        ('jasrac', 'JASRAC (Japan)'),
        ('socan', 'SOCAN (Canada)'),
        ('apra', 'APRA (Australia)'),
        ('unknown', 'Unknown/Unaffiliated'),
    ]
    
    # Core identification
    detection_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    session_id = models.UUIDField(db_index=True)
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='audio_detections')
    
    # Track information
    track = models.ForeignKey(Track, on_delete=models.CASCADE, null=True, blank=True, related_name='detections')
    detected_title = models.CharField(max_length=500, null=True, blank=True)
    detected_artist = models.CharField(max_length=500, null=True, blank=True)
    detected_album = models.CharField(max_length=500, null=True, blank=True)
    
    # Detection metadata
    detection_source = models.CharField(max_length=20, choices=DETECTION_SOURCES, default='local')
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default='pending')
    
    # External identification
    isrc = models.CharField(max_length=12, null=True, blank=True, db_index=True)
    iswc = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    pro_affiliation = models.CharField(max_length=20, choices=PRO_AFFILIATIONS, null=True, blank=True)
    
    # Fingerprint data
    audio_fingerprint = models.TextField(null=True, blank=True)
    fingerprint_version = models.CharField(max_length=10, default='1.0')
    audio_segment_hash = models.CharField(max_length=64, null=True, blank=True)
    
    # Timing information
    detected_at = models.DateTimeField(auto_now_add=True)
    audio_timestamp = models.DateTimeField()
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Processing metadata
    processing_time_ms = models.IntegerField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    
    # External service data
    acrcloud_response = models.JSONField(default=dict, blank=True)
    external_metadata = models.JSONField(default=dict, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['station', 'detected_at']),
            models.Index(fields=['detection_source', 'confidence_score']),
            models.Index(fields=['isrc']),
            models.Index(fields=['pro_affiliation', 'detected_at']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['session_id', 'audio_timestamp']),
        ]
        ordering = ['-detected_at']
    
    def __str__(self):
        title = self.detected_title or (self.track.title if self.track else 'Unknown')
        return f"Detection: {title} on {self.station.name} ({self.detection_source})"
    
    def mark_processing_complete(self, track=None, confidence=None):
        """Mark detection as completed with optional track assignment"""
        self.processing_status = 'completed'
        if track:
            self.track = track
        if confidence is not None:
            self.confidence_score = confidence
        self.save()
    
    def mark_processing_failed(self, error_message):
        """Mark detection as failed with error message"""
        self.processing_status = 'failed'
        self.error_message = error_message
        self.save()
    
    def increment_retry(self):
        """Increment retry count and set status to retry"""
        self.retry_count += 1
        self.processing_status = 'retry'
        self.save()
    
    def is_high_confidence(self):
        """Check if detection has high confidence score"""
        return self.confidence_score >= 0.8
    
    def get_pro_display_name(self):
        """Get human-readable PRO name"""
        pro_names = dict(self.PRO_AFFILIATIONS)
        return pro_names.get(self.pro_affiliation, 'Unknown')


class RoyaltyDistribution(models.Model):
    """Enhanced royalty distribution model for complex royalty splitting"""
    RECIPIENT_TYPES = [
        ('artist', 'Artist'),
        ('publisher', 'Publisher'),
        ('contributor', 'Contributor'),
        ('pro', 'Performing Rights Organization'),
        ('external_pro', 'External PRO (Reciprocal)'),
    ]
    
    DISTRIBUTION_STATUS = [
        ('pending', 'Pending Calculation'),
        ('calculated', 'Calculated'),
        ('approved', 'Approved for Payment'),
        ('paid', 'Paid'),
        ('failed', 'Payment Failed'),
        ('disputed', 'Under Dispute'),
        ('withheld', 'Withheld'),
    ]
    
    CURRENCY_CHOICES = [
        ('GHS', 'Ghana Cedi'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]
    
    # Core identification
    distribution_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    
    # Source information
    play_log = models.ForeignKey(PlayLog, on_delete=models.CASCADE, related_name='royalty_distributions')
    audio_detection = models.ForeignKey(AudioDetection, on_delete=models.CASCADE, null=True, blank=True, related_name='royalty_distributions')
    
    # Recipient information
    recipient = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='received_royalties')
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPES)
    
    # Financial details
    gross_amount = models.DecimalField(max_digits=12, decimal_places=4)
    net_amount = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GHS')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)
    
    # Split information
    percentage_split = models.DecimalField(max_digits=5, decimal_places=2)
    contributor_role = models.CharField(max_length=50, null=True, blank=True)
    
    # PRO and external routing
    pro_share = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    external_pro = models.ForeignKey('royalties.PartnerPRO', on_delete=models.SET_NULL, null=True, blank=True)
    reciprocal_agreement = models.ForeignKey('royalties.ReciprocalAgreement', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Processing information
    calculated_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=DISTRIBUTION_STATUS, default='pending')
    
    # Payment details
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    payment_fee = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    # Audit and metadata
    calculation_metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='created_distributions')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['play_log', 'recipient_type']),
            models.Index(fields=['status', 'calculated_at']),
            models.Index(fields=['external_pro', 'status']),
            models.Index(fields=['currency', 'calculated_at']),
        ]
        ordering = ['-calculated_at']
    
    def __str__(self):
        return f"Royalty: {self.net_amount} {self.currency} to {self.recipient.email} ({self.recipient_type})"
    
    def approve_for_payment(self, approved_by):
        """Approve distribution for payment"""
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.save()
    
    def mark_as_paid(self, payment_reference, payment_method=None):
        """Mark distribution as paid"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.payment_reference = payment_reference
        if payment_method:
            self.payment_method = payment_method
        self.save()
    
    def mark_as_failed(self, reason):
        """Mark payment as failed"""
        self.status = 'failed'
        self.notes = f"{self.notes}\nPayment failed: {reason}" if self.notes else f"Payment failed: {reason}"
        self.save()
    
    def calculate_net_amount(self):
        """Calculate net amount after fees"""
        self.net_amount = self.gross_amount - self.payment_fee
        return self.net_amount
    
    def is_international_payment(self):
        """Check if this is an international payment"""
        return self.external_pro is not None or self.currency != 'GHS'


class SnippetIngest(models.Model):
    """Idempotency tracking for device-uploaded snippets."""
    chunk_id = models.CharField(max_length=255, unique=True)
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="snippet_ingests")
    started_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.chunk_id} for {self.station.name}"
