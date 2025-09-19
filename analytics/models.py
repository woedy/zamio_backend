import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class AnalyticsSnapshot(models.Model):
    """Time-series snapshots for efficient analytics queries"""
    SNAPSHOT_TYPES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    METRIC_TYPES = [
        ('plays', 'Play Count'),
        ('revenue', 'Revenue'),
        ('detections', 'Detection Count'),
        ('confidence', 'Average Confidence'),
        ('unique_tracks', 'Unique Tracks'),
        ('unique_stations', 'Unique Stations'),
        ('system_health', 'System Health'),
    ]
    
    snapshot_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    snapshot_type = models.CharField(max_length=20, choices=SNAPSHOT_TYPES)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    
    # Time period
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField(db_index=True)
    
    # Aggregated data
    value = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Dimensions for filtering
    artist_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    station_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    publisher_id = models.IntegerField(null=True, blank=True, db_index=True)
    track_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    region = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['snapshot_type', 'metric_type', 'period_start']),
            models.Index(fields=['artist_id', 'metric_type', 'period_start']),
            models.Index(fields=['station_id', 'metric_type', 'period_start']),
            models.Index(fields=['publisher_id', 'metric_type', 'period_start']),
            models.Index(fields=['region', 'metric_type', 'period_start']),
        ]
        unique_together = [
            ('snapshot_type', 'metric_type', 'period_start', 'artist_id', 'station_id', 'publisher_id', 'track_id', 'region')
        ]
    
    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.get_snapshot_type_display()} ({self.period_start.date()})"


class AnalyticsCache(models.Model):
    """Redis-backed cache entries for frequently accessed analytics"""
    CACHE_TYPES = [
        ('dashboard', 'Dashboard Data'),
        ('report', 'Report Data'),
        ('export', 'Export Data'),
        ('realtime', 'Real-time Data'),
    ]
    
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    cache_type = models.CharField(max_length=20, choices=CACHE_TYPES)
    
    # Cache metadata
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    parameters = models.JSONField(default=dict, blank=True)
    
    # Cache timing
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    last_accessed = models.DateTimeField(auto_now=True)
    access_count = models.IntegerField(default=0)
    
    # Cache size tracking
    data_size_bytes = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['cache_type', 'expires_at']),
            models.Index(fields=['user_id', 'cache_type']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Cache: {self.cache_key} ({self.get_cache_type_display()})"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def increment_access(self):
        self.access_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['access_count', 'last_accessed'])


class RealtimeMetric(models.Model):
    """Real-time metrics for WebSocket updates"""
    METRIC_NAMES = [
        ('active_detections', 'Active Detections'),
        ('processing_queue', 'Processing Queue Size'),
        ('system_load', 'System Load'),
        ('error_rate', 'Error Rate'),
        ('revenue_today', 'Revenue Today'),
        ('plays_today', 'Plays Today'),
    ]
    
    metric_name = models.CharField(max_length=50, choices=METRIC_NAMES, db_index=True)
    value = models.DecimalField(max_digits=15, decimal_places=4)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Dimensions
    station_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    artist_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['metric_name', 'timestamp']),
            models.Index(fields=['station_id', 'metric_name', 'timestamp']),
            models.Index(fields=['artist_id', 'metric_name', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_metric_name_display()}: {self.value} ({self.timestamp})"


class AnalyticsExport(models.Model):
    """Track analytics export requests and files"""
    EXPORT_FORMATS = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ]
    
    EXPORT_TYPES = [
        ('artist_analytics', 'Artist Analytics'),
        ('publisher_analytics', 'Publisher Analytics'),
        ('station_analytics', 'Station Analytics'),
        ('admin_analytics', 'Admin Analytics'),
        ('royalty_report', 'Royalty Report'),
        ('detection_report', 'Detection Report'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    export_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_exports')
    
    export_type = models.CharField(max_length=30, choices=EXPORT_TYPES)
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    
    # Export parameters
    parameters = models.JSONField(default=dict, blank=True)
    date_range_start = models.DateTimeField(null=True, blank=True)
    date_range_end = models.DateTimeField(null=True, blank=True)
    
    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.IntegerField(default=0)
    
    # File information
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size_bytes = models.IntegerField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    
    # Timing
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['export_type', 'requested_at']),
            models.Index(fields=['status', 'requested_at']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.get_export_type_display()} - {self.get_export_format_display()} ({self.status})"
    
    def mark_processing(self):
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self, file_path, file_size=None):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.file_path = file_path
        self.progress_percentage = 100
        if file_size:
            self.file_size_bytes = file_size
        # Set expiration to 7 days from completion
        self.expires_at = timezone.now() + timezone.timedelta(days=7)
        self.save()
    
    def mark_failed(self, error_message):
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])
    
    def increment_download(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])
    
    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at


class UserAnalyticsPreference(models.Model):
    """User preferences for analytics dashboards"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='analytics_preferences')
    
    # Dashboard preferences
    default_date_range = models.CharField(
        max_length=20,
        choices=[
            ('7d', 'Last 7 Days'),
            ('30d', 'Last 30 Days'),
            ('90d', 'Last 90 Days'),
            ('1y', 'Last Year'),
            ('custom', 'Custom Range'),
        ],
        default='30d'
    )
    
    # Widget preferences
    dashboard_layout = models.JSONField(default=dict, blank=True)
    favorite_metrics = models.JSONField(default=list, blank=True)
    
    # Notification preferences
    email_reports = models.BooleanField(default=True)
    report_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('never', 'Never'),
        ],
        default='weekly'
    )
    
    # Export preferences
    preferred_export_format = models.CharField(
        max_length=10,
        choices=AnalyticsExport.EXPORT_FORMATS,
        default='csv'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Analytics Preferences for {self.user.email}"