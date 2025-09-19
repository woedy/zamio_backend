from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Dispute, DisputeEvidence, DisputeAuditLog, DisputeComment,
    DisputeWorkflowRule, DisputeNotification
)


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'dispute_id_short', 'title', 'dispute_type', 'status', 'priority',
        'submitted_by', 'assigned_to', 'created_at', 'days_open'
    ]
    list_filter = [
        'status', 'dispute_type', 'priority', 'created_at', 'resolved_at'
    ]
    search_fields = [
        'dispute_id', 'title', 'description', 'submitted_by__username',
        'submitted_by__email'
    ]
    readonly_fields = [
        'dispute_id', 'created_at', 'updated_at', 'resolved_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('dispute_id', 'title', 'description', 'dispute_type')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'assigned_to')
        }),
        ('Parties', {
            'fields': ('submitted_by',)
        }),
        ('Related Objects', {
            'fields': ('related_track', 'related_detection', 'related_royalty', 'related_station'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolution_summary', 'resolution_action_taken'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )
    
    def dispute_id_short(self, obj):
        return str(obj.dispute_id)[:8] + '...'
    dispute_id_short.short_description = 'Dispute ID'
    
    def days_open(self, obj):
        if obj.resolved_at:
            delta = obj.resolved_at - obj.created_at
        else:
            delta = timezone.now() - obj.created_at
        return delta.days
    days_open.short_description = 'Days Open'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'submitted_by', 'assigned_to', 'related_track', 'related_station'
        )


class DisputeEvidenceInline(admin.TabularInline):
    model = DisputeEvidence
    extra = 0
    readonly_fields = ['uploaded_at']
    fields = ['title', 'description', 'file', 'uploaded_by', 'uploaded_at']


class DisputeCommentInline(admin.TabularInline):
    model = DisputeComment
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = ['author', 'content', 'is_internal', 'created_at']


@admin.register(DisputeEvidence)
class DisputeEvidenceAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'dispute_link', 'uploaded_by', 'file_type', 'uploaded_at'
    ]
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['title', 'description', 'dispute__title']
    readonly_fields = ['uploaded_at', 'file_size']
    
    def dispute_link(self, obj):
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">{}</a>', url, obj.dispute.title)
    dispute_link.short_description = 'Dispute'


@admin.register(DisputeAuditLog)
class DisputeAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'dispute_link', 'actor', 'action', 'previous_state', 'new_state', 'timestamp'
    ]
    list_filter = ['action', 'previous_state', 'new_state', 'timestamp']
    search_fields = ['dispute__title', 'actor__username', 'description']
    readonly_fields = ['timestamp']
    
    def dispute_link(self, obj):
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.dispute.dispute_id)[:8])
    dispute_link.short_description = 'Dispute'
    
    def has_add_permission(self, request):
        return False  # Audit logs should only be created programmatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Audit logs should be immutable


@admin.register(DisputeComment)
class DisputeCommentAdmin(admin.ModelAdmin):
    list_display = [
        'dispute_link', 'author', 'content_preview', 'is_internal', 'created_at'
    ]
    list_filter = ['is_internal', 'created_at']
    search_fields = ['dispute__title', 'author__username', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def dispute_link(self, obj):
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.dispute.dispute_id)[:8])
    dispute_link.short_description = 'Dispute'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(DisputeWorkflowRule)
class DisputeWorkflowRuleAdmin(admin.ModelAdmin):
    list_display = [
        'from_status', 'to_status', 'required_role', 'requires_evidence',
        'auto_transition', 'is_active'
    ]
    list_filter = ['is_active', 'auto_transition', 'requires_evidence']
    search_fields = ['from_status', 'to_status', 'required_role']


@admin.register(DisputeNotification)
class DisputeNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'dispute_link', 'recipient', 'notification_type', 'title',
        'sent_at', 'read_at', 'email_sent'
    ]
    list_filter = ['notification_type', 'email_sent', 'sms_sent', 'sent_at']
    search_fields = ['dispute__title', 'recipient__username', 'title']
    readonly_fields = ['sent_at']
    
    def dispute_link(self, obj):
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.dispute.dispute_id)[:8])
    dispute_link.short_description = 'Dispute'


# Customize the admin site
admin.site.site_header = "ZamIO Dispute Management"
admin.site.site_title = "ZamIO Disputes"
admin.site.index_title = "Dispute Resolution System"