from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    AnalyticsSnapshot, AnalyticsCache, RealtimeMetric, 
    AnalyticsExport, UserAnalyticsPreference
)


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        'snapshot_id', 'snapshot_type', 'metric_type', 
        'period_start', 'value', 'count', 'created_at'
    ]
    list_filter = [
        'snapshot_type', 'metric_type', 'period_start', 
        'region', 'created_at'
    ]
    search_fields = [
        'snapshot_id', 'artist_id', 'station_id', 'track_id'
    ]
    readonly_fields = ['snapshot_id', 'created_at']
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('snapshot_id', 'snapshot_type', 'metric_type')
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Data', {
            'fields': ('value', 'count', 'metadata')
        }),
        ('Dimensions', {
            'fields': ('artist_id', 'station_id', 'publisher_id', 'track_id', 'region'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(admin.ModelAdmin):
    list_display = [
        'cache_key', 'cache_type', 'user_id', 
        'created_at', 'expires_at', 'access_count', 
        'data_size_display', 'is_expired_display'
    ]
    list_filter = [
        'cache_type', 'created_at', 'expires_at'
    ]
    search_fields = ['cache_key', 'user_id']
    readonly_fields = ['created_at', 'last_accessed']
    date_hierarchy = 'created_at'
    
    def data_size_display(self, obj):
        """Display data size in human readable format"""
        size = obj.data_size_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    data_size_display.short_description = 'Data Size'
    
    def is_expired_display(self, obj):
        """Display expiration status with color coding"""
        if obj.is_expired():
            return format_html(
                '<span style="color: red;">Expired</span>'
            )
        else:
            return format_html(
                '<span style="color: green;">Active</span>'
            )
    is_expired_display.short_description = 'Status'
    
    actions = ['cleanup_expired_cache']
    
    def cleanup_expired_cache(self, request, queryset):
        """Admin action to cleanup expired cache entries"""
        expired_count = queryset.filter(expires_at__lt=timezone.now()).count()
        queryset.filter(expires_at__lt=timezone.now()).delete()
        self.message_user(request, f"Cleaned up {expired_count} expired cache entries.")
    cleanup_expired_cache.short_description = "Clean up expired cache entries"


@admin.register(RealtimeMetric)
class RealtimeMetricAdmin(admin.ModelAdmin):
    list_display = [
        'metric_name', 'value', 'station_id', 'artist_id', 'timestamp'
    ]
    list_filter = [
        'metric_name', 'timestamp'
    ]
    search_fields = ['metric_name', 'station_id', 'artist_id']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        # Only show recent metrics (last 24 hours) for performance
        return super().get_queryset(request).filter(
            timestamp__gte=timezone.now() - timezone.timedelta(days=1)
        )


@admin.register(AnalyticsExport)
class AnalyticsExportAdmin(admin.ModelAdmin):
    list_display = [
        'export_id', 'user', 'export_type', 'export_format',
        'status', 'progress_percentage', 'requested_at', 
        'file_size_display', 'download_count'
    ]
    list_filter = [
        'export_type', 'export_format', 'status', 
        'requested_at', 'completed_at'
    ]
    search_fields = ['export_id', 'user__email', 'user__username']
    readonly_fields = [
        'export_id', 'requested_at', 'started_at', 
        'completed_at', 'download_count'
    ]
    date_hierarchy = 'requested_at'
    
    fieldsets = (
        ('Export Information', {
            'fields': ('export_id', 'user', 'export_type', 'export_format')
        }),
        ('Parameters', {
            'fields': ('parameters', 'date_range_start', 'date_range_end'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'progress_percentage', 'error_message')
        }),
        ('File Information', {
            'fields': ('file_path', 'file_size_bytes', 'download_count')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'started_at', 'completed_at', 'expires_at'),
            'classes': ('collapse',)
        })
    )
    
    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if not obj.file_size_bytes:
            return "N/A"
        
        size = obj.file_size_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = 'File Size'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    actions = ['cleanup_expired_exports', 'retry_failed_exports']
    
    def cleanup_expired_exports(self, request, queryset):
        """Admin action to cleanup expired exports"""
        expired_count = queryset.filter(
            expires_at__lt=timezone.now(),
            status='completed'
        ).count()
        queryset.filter(
            expires_at__lt=timezone.now(),
            status='completed'
        ).delete()
        self.message_user(request, f"Cleaned up {expired_count} expired exports.")
    cleanup_expired_exports.short_description = "Clean up expired exports"
    
    def retry_failed_exports(self, request, queryset):
        """Admin action to retry failed exports"""
        failed_exports = queryset.filter(status='failed')
        count = 0
        for export in failed_exports:
            export.status = 'pending'
            export.error_message = None
            export.save()
            # Re-queue the task
            from .tasks import generate_analytics_export
            generate_analytics_export.delay(export.export_id)
            count += 1
        
        self.message_user(request, f"Retried {count} failed exports.")
    retry_failed_exports.short_description = "Retry failed exports"


@admin.register(UserAnalyticsPreference)
class UserAnalyticsPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'default_date_range', 'email_reports', 
        'report_frequency', 'preferred_export_format', 'updated_at'
    ]
    list_filter = [
        'default_date_range', 'email_reports', 'report_frequency',
        'preferred_export_format', 'updated_at'
    ]
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Dashboard Preferences', {
            'fields': ('default_date_range', 'dashboard_layout', 'favorite_metrics')
        }),
        ('Notification Preferences', {
            'fields': ('email_reports', 'report_frequency')
        }),
        ('Export Preferences', {
            'fields': ('preferred_export_format',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# Custom admin views for analytics overview
class AnalyticsOverviewAdmin(admin.ModelAdmin):
    """Custom admin view for analytics overview"""
    
    def changelist_view(self, request, extra_context=None):
        # Add analytics summary to context
        extra_context = extra_context or {}
        
        # Get recent metrics
        recent_exports = AnalyticsExport.objects.filter(
            requested_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        
        active_cache_entries = AnalyticsCache.objects.filter(
            expires_at__gt=timezone.now()
        ).count()
        
        recent_snapshots = AnalyticsSnapshot.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=1)
        ).count()
        
        extra_context.update({
            'recent_exports': recent_exports,
            'active_cache_entries': active_cache_entries,
            'recent_snapshots': recent_snapshots,
        })
        
        return super().changelist_view(request, extra_context)


# Register the overview admin
admin.site.register_view('analytics/overview/', view=AnalyticsOverviewAdmin.changelist_view, name='Analytics Overview')