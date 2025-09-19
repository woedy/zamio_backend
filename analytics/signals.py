from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from decimal import Decimal

from music_monitor.models import PlayLog, AudioDetection, RoyaltyDistribution
from .services import analytics_aggregator


@receiver(post_save, sender=PlayLog)
def handle_playlog_created(sender, instance, created, **kwargs):
    """Handle new play log creation for real-time updates"""
    if created and instance.active:
        # Update real-time metrics
        analytics_aggregator.update_realtime_metric(
            'plays_today',
            Decimal('1'),
            metadata={'station_id': instance.station.station_id if instance.station else None}
        )
        
        # Invalidate relevant cache
        if instance.track and instance.track.artist:
            analytics_aggregator.invalidate_cache_pattern(f"artist_analytics:artist_id:{instance.track.artist.artist_id}*")
        
        if instance.station:
            analytics_aggregator.invalidate_cache_pattern(f"station_analytics:station_id:{instance.station.station_id}*")
        
        # Send WebSocket update to relevant groups
        channel_layer = get_channel_layer()
        
        # Update artist analytics
        if instance.track and instance.track.artist:
            async_to_sync(channel_layer.group_send)(
                f"analytics_artist_{instance.track.artist.artist_id}",
                {
                    'type': 'analytics_update',
                    'data': {
                        'type': 'new_play',
                        'track_title': instance.track.title,
                        'station_name': instance.station.name if instance.station else 'Unknown',
                        'royalty_amount': float(instance.royalty_amount or 0)
                    }
                }
            )
        
        # Update station analytics
        if instance.station:
            async_to_sync(channel_layer.group_send)(
                f"analytics_station_{instance.station.station_id}",
                {
                    'type': 'analytics_update',
                    'data': {
                        'type': 'new_play',
                        'track_title': instance.track.title if instance.track else 'Unknown',
                        'artist_name': instance.track.artist.stage_name if instance.track and instance.track.artist else 'Unknown'
                    }
                }
            )


@receiver(post_save, sender=AudioDetection)
def handle_detection_created(sender, instance, created, **kwargs):
    """Handle new audio detection for real-time updates"""
    if created:
        # Update detection metrics
        analytics_aggregator.update_realtime_metric(
            'active_detections',
            Decimal('1'),
            station_id=instance.station.station_id if instance.station else None
        )
        
        # Send WebSocket update for processing status
        channel_layer = get_channel_layer()
        
        if instance.station:
            async_to_sync(channel_layer.group_send)(
                f"analytics_station_{instance.station.station_id}",
                {
                    'type': 'analytics_update',
                    'data': {
                        'type': 'new_detection',
                        'confidence_score': float(instance.confidence_score),
                        'detection_source': instance.detection_source,
                        'processing_status': instance.processing_status
                    }
                }
            )


@receiver(post_save, sender=RoyaltyDistribution)
def handle_royalty_distribution_created(sender, instance, created, **kwargs):
    """Handle new royalty distribution for real-time updates"""
    if created:
        # Update revenue metrics
        analytics_aggregator.update_realtime_metric(
            'revenue_today',
            instance.net_amount,
            metadata={'recipient_type': instance.recipient_type}
        )
        
        # Invalidate cache for recipient
        if instance.recipient_type == 'artist':
            try:
                artist = instance.recipient.artists.filter(active=True).first()
                if artist:
                    analytics_aggregator.invalidate_cache_pattern(f"artist_analytics:artist_id:{artist.artist_id}*")
            except:
                pass
        
        # Send WebSocket update
        channel_layer = get_channel_layer()
        
        async_to_sync(channel_layer.group_send)(
            f"analytics_user_{instance.recipient.id}",
            {
                'type': 'analytics_update',
                'data': {
                    'type': 'new_royalty',
                    'amount': float(instance.net_amount),
                    'currency': instance.currency,
                    'status': instance.status
                }
            }
        )


@receiver(post_save, sender=AudioDetection)
def handle_detection_status_update(sender, instance, created, **kwargs):
    """Handle detection status updates"""
    if not created:  # Only for updates
        # Send processing status update
        channel_layer = get_channel_layer()
        
        if instance.station:
            async_to_sync(channel_layer.group_send)(
                f"analytics_station_{instance.station.station_id}",
                {
                    'type': 'analytics_update',
                    'data': {
                        'type': 'detection_status_update',
                        'detection_id': str(instance.detection_id),
                        'processing_status': instance.processing_status,
                        'confidence_score': float(instance.confidence_score),
                        'error_message': instance.error_message
                    }
                }
            )
        
        # Update error rate if detection failed
        if instance.processing_status == 'failed':
            analytics_aggregator.update_realtime_metric(
                'error_rate',
                Decimal('1'),
                metadata={'error_type': 'detection_failed'}
            )


# Cache invalidation helpers
def invalidate_analytics_cache_for_artist(artist_id):
    """Invalidate all analytics cache for an artist"""
    analytics_aggregator.invalidate_cache_pattern(f"artist_analytics:artist_id:{artist_id}*")


def invalidate_analytics_cache_for_station(station_id):
    """Invalidate all analytics cache for a station"""
    analytics_aggregator.invalidate_cache_pattern(f"station_analytics:station_id:{station_id}*")


def invalidate_analytics_cache_for_publisher(publisher_id):
    """Invalidate all analytics cache for a publisher"""
    analytics_aggregator.invalidate_cache_pattern(f"publisher_analytics:publisher_id:{publisher_id}*")