import os
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import AnalyticsExport, AnalyticsSnapshot, RealtimeMetric
from .services import analytics_aggregator
from music_monitor.models import PlayLog, AudioDetection


@shared_task(bind=True)
def generate_analytics_export(self, export_id):
    """Generate analytics export file"""
    try:
        export_request = AnalyticsExport.objects.get(export_id=export_id)
        export_request.mark_processing()
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 10})
        
        # Generate data based on export type
        if export_request.export_type == 'artist_analytics':
            data = generate_artist_export_data(export_request)
        elif export_request.export_type == 'publisher_analytics':
            data = generate_publisher_export_data(export_request)
        elif export_request.export_type == 'station_analytics':
            data = generate_station_export_data(export_request)
        elif export_request.export_type == 'admin_analytics':
            data = generate_admin_export_data(export_request)
        elif export_request.export_type == 'royalty_report':
            data = generate_royalty_export_data(export_request)
        elif export_request.export_type == 'detection_report':
            data = generate_detection_export_data(export_request)
        else:
            raise ValueError(f"Unknown export type: {export_request.export_type}")
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 50})
        
        # Generate file based on format
        file_path = None
        if export_request.export_format == 'csv':
            file_path = generate_csv_file(data, export_request)
        elif export_request.export_format == 'excel':
            file_path = generate_excel_file(data, export_request)
        elif export_request.export_format == 'pdf':
            file_path = generate_pdf_file(data, export_request)
        elif export_request.export_format == 'json':
            file_path = generate_json_file(data, export_request)
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 90})
        
        # Get file size
        file_size = default_storage.size(file_path) if file_path else 0
        
        # Mark as completed
        export_request.mark_completed(file_path, file_size)
        
        # Send WebSocket notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"analytics_user_{export_request.user.id}",
            {
                'type': 'export_completed',
                'export_id': str(export_request.export_id),
                'file_path': file_path
            }
        )
        
        return {'status': 'completed', 'file_path': file_path}
        
    except AnalyticsExport.DoesNotExist:
        return {'status': 'error', 'message': 'Export request not found'}
    except Exception as e:
        try:
            export_request.mark_failed(str(e))
        except:
            pass
        return {'status': 'error', 'message': str(e)}


@shared_task
def create_analytics_snapshots():
    """Create time-series snapshots for efficient analytics queries"""
    try:
        now = timezone.now()
        
        # Create hourly snapshots
        create_hourly_snapshots(now)
        
        # Create daily snapshots (run once per day)
        if now.hour == 1:  # Run at 1 AM
            create_daily_snapshots(now)
        
        # Create weekly snapshots (run on Sundays)
        if now.weekday() == 6 and now.hour == 2:  # Sunday at 2 AM
            create_weekly_snapshots(now)
        
        # Create monthly snapshots (run on 1st of month)
        if now.day == 1 and now.hour == 3:  # 1st of month at 3 AM
            create_monthly_snapshots(now)
        
        return {'status': 'completed'}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task
def update_realtime_metrics():
    """Update real-time metrics"""
    try:
        now = timezone.now()
        
        # Active detections (last 5 minutes)
        active_detections = AudioDetection.objects.filter(
            detected_at__gte=now - timedelta(minutes=5),
            processing_status='processing'
        ).count()
        
        analytics_aggregator.update_realtime_metric(
            'active_detections',
            Decimal(active_detections)
        )
        
        # Processing queue size
        queue_size = AudioDetection.objects.filter(
            processing_status='pending'
        ).count()
        
        analytics_aggregator.update_realtime_metric(
            'processing_queue',
            Decimal(queue_size)
        )
        
        # Revenue today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        revenue_today = PlayLog.objects.filter(
            played_at__gte=today_start,
            active=True
        ).aggregate(
            total=models.Sum('royalty_amount')
        )['total'] or Decimal('0')
        
        analytics_aggregator.update_realtime_metric(
            'revenue_today',
            revenue_today
        )
        
        # Plays today
        plays_today = PlayLog.objects.filter(
            played_at__gte=today_start,
            active=True
        ).count()
        
        analytics_aggregator.update_realtime_metric(
            'plays_today',
            Decimal(plays_today)
        )
        
        # Error rate (last hour)
        hour_ago = now - timedelta(hours=1)
        total_detections = AudioDetection.objects.filter(
            detected_at__gte=hour_ago
        ).count()
        
        failed_detections = AudioDetection.objects.filter(
            detected_at__gte=hour_ago,
            processing_status='failed'
        ).count()
        
        error_rate = 0
        if total_detections > 0:
            error_rate = (failed_detections / total_detections) * 100
        
        analytics_aggregator.update_realtime_metric(
            'error_rate',
            Decimal(str(error_rate))
        )
        
        # Send WebSocket updates
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "realtime_metrics",
            {
                'type': 'realtime_update',
                'metrics': {
                    'active_detections': active_detections,
                    'processing_queue': queue_size,
                    'revenue_today': float(revenue_today),
                    'plays_today': plays_today,
                    'error_rate': float(error_rate)
                },
                'timestamp': now.isoformat()
            }
        )
        
        return {'status': 'completed'}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task
def cleanup_analytics_data():
    """Clean up old analytics data and cache"""
    try:
        now = timezone.now()
        
        # Clean up old real-time metrics (keep last 7 days)
        cutoff_date = now - timedelta(days=7)
        RealtimeMetric.objects.filter(timestamp__lt=cutoff_date).delete()
        
        # Clean up expired exports
        AnalyticsExport.objects.filter(
            expires_at__lt=now,
            status='completed'
        ).delete()
        
        # Clean up failed exports older than 1 day
        failed_cutoff = now - timedelta(days=1)
        AnalyticsExport.objects.filter(
            requested_at__lt=failed_cutoff,
            status='failed'
        ).delete()
        
        # Clean up Redis cache
        analytics_aggregator.cleanup_expired_cache()
        
        return {'status': 'completed'}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def generate_artist_export_data(export_request):
    """Generate artist analytics export data"""
    # Get date range
    if export_request.date_range_start and export_request.date_range_end:
        date_range = (export_request.date_range_start, export_request.date_range_end)
    else:
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        date_range = (start_date, end_date)
    
    # Get artist ID from parameters or user
    artist_id = export_request.parameters.get('artist_id')
    if not artist_id:
        artist = export_request.user.artists.filter(active=True).first()
        artist_id = artist.artist_id if artist else None
    
    if not artist_id:
        return []
    
    # Get analytics data
    analytics_data = analytics_aggregator.get_artist_analytics(artist_id, date_range)
    
    # Convert to export format
    export_data = []
    for day_data in analytics_data.get('daily_trends', []):
        export_data.append({
            'Date': day_data['date'],
            'Plays': day_data['plays'],
            'Revenue': day_data['revenue']
        })
    
    return export_data


def generate_csv_file(data, export_request):
    """Generate CSV file from data"""
    if not data:
        return None
    
    filename = f"analytics_export_{export_request.export_id}.csv"
    file_path = f"exports/{filename}"
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.join(settings.MEDIA_ROOT, file_path)), exist_ok=True)
    
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    return file_path


def generate_json_file(data, export_request):
    """Generate JSON file from data"""
    filename = f"analytics_export_{export_request.export_id}.json"
    file_path = f"exports/{filename}"
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.join(settings.MEDIA_ROOT, file_path)), exist_ok=True)
    
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, indent=2, default=str)
    
    return file_path


def generate_excel_file(data, export_request):
    """Generate Excel file from data"""
    try:
        import pandas as pd
        
        filename = f"analytics_export_{export_request.export_id}.xlsx"
        file_path = f"exports/{filename}"
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.join(settings.MEDIA_ROOT, file_path)), exist_ok=True)
        
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        # Convert data to DataFrame and save as Excel
        df = pd.DataFrame(data)
        df.to_excel(full_path, index=False)
        
        return file_path
        
    except ImportError:
        # Fallback to CSV if pandas not available
        return generate_csv_file(data, export_request)


def generate_pdf_file(data, export_request):
    """Generate PDF file from data"""
    # This would require a PDF generation library like ReportLab
    # For now, fallback to CSV
    return generate_csv_file(data, export_request)


def create_hourly_snapshots(now):
    """Create hourly analytics snapshots"""
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    hour_end = hour_start + timedelta(hours=1)
    
    # Create snapshots for plays, revenue, detections
    # Implementation would aggregate data for the hour
    pass


def create_daily_snapshots(now):
    """Create daily analytics snapshots"""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    # Create snapshots for the previous day
    # Implementation would aggregate data for the day
    pass


def create_weekly_snapshots(now):
    """Create weekly analytics snapshots"""
    # Implementation for weekly snapshots
    pass


def create_monthly_snapshots(now):
    """Create monthly analytics snapshots"""
    # Implementation for monthly snapshots
    pass


# Additional export data generators
def generate_publisher_export_data(export_request):
    """Generate publisher analytics export data"""
    # Implementation for publisher export
    return []


def generate_station_export_data(export_request):
    """Generate station analytics export data"""
    # Implementation for station export
    return []


def generate_admin_export_data(export_request):
    """Generate admin analytics export data"""
    # Implementation for admin export
    return []


def generate_royalty_export_data(export_request):
    """Generate royalty report export data"""
    # Implementation for royalty export
    return []


def generate_detection_export_data(export_request):
    """Generate detection report export data"""
    # Implementation for detection export
    return []