import json
import redis
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from django.db import models
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import AnalyticsSnapshot, AnalyticsCache, RealtimeMetric
from music_monitor.models import PlayLog, AudioDetection, RoyaltyDistribution
from artists.models import Artist, Track
from stations.models import Station
from publishers.models import PublisherProfile

User = get_user_model()


class AnalyticsAggregator:
    """Service for efficient analytics data processing and aggregation"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_ANALYTICS_DB', 1),
            decode_responses=True
        )
        self.cache_prefix = 'analytics:'
        self.default_cache_timeout = 3600  # 1 hour
    
    def generate_cache_key(self, key_type: str, **params) -> str:
        """Generate consistent cache keys"""
        param_str = '_'.join([f"{k}:{v}" for k, v in sorted(params.items()) if v is not None])
        return f"{self.cache_prefix}{key_type}:{param_str}"
    
    def get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """Get data from Redis cache"""
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except (redis.RedisError, json.JSONDecodeError):
            pass
        return None
    
    def set_cached_data(self, cache_key: str, data: Dict, timeout: int = None) -> bool:
        """Set data in Redis cache"""
        try:
            timeout = timeout or self.default_cache_timeout
            serialized_data = json.dumps(data, default=str)
            return self.redis_client.setex(cache_key, timeout, serialized_data)
        except (redis.RedisError, json.JSONEncodeError):
            return False
    
    def invalidate_cache_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        try:
            keys = self.redis_client.keys(f"{self.cache_prefix}{pattern}")
            if keys:
                self.redis_client.delete(*keys)
        except redis.RedisError:
            pass
    
    def get_artist_analytics(self, artist_id: str, date_range: Tuple[datetime, datetime]) -> Dict:
        """Get comprehensive analytics for an artist"""
        start_date, end_date = date_range
        cache_key = self.generate_cache_key(
            'artist_analytics',
            artist_id=artist_id,
            start=start_date.date(),
            end=end_date.date()
        )
        
        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        # Get artist and their tracks
        try:
            artist = Artist.objects.get(artist_id=artist_id)
            tracks = Track.objects.filter(artist=artist, active=True)
            track_ids = list(tracks.values_list('track_id', flat=True))
        except Artist.DoesNotExist:
            return {}
        
        # Base queryset for the date range
        play_logs = PlayLog.objects.filter(
            track__track_id__in=track_ids,
            played_at__range=(start_date, end_date),
            active=True
        )
        
        # Aggregate basic metrics
        basic_metrics = play_logs.aggregate(
            total_plays=Count('id'),
            total_revenue=Sum('royalty_amount') or Decimal('0'),
            avg_confidence=Avg('avg_confidence_score') or Decimal('0'),
            unique_stations=Count('station', distinct=True)
        )
        
        # Top performing tracks
        top_tracks = play_logs.values(
            'track__title', 'track__track_id'
        ).annotate(
            play_count=Count('id'),
            revenue=Sum('royalty_amount') or Decimal('0')
        ).order_by('-play_count')[:10]
        
        # Geographic distribution
        geographic_data = play_logs.values(
            'station__region', 'station__city'
        ).annotate(
            play_count=Count('id'),
            revenue=Sum('royalty_amount') or Decimal('0')
        ).order_by('-play_count')[:20]
        
        # Time series data (daily aggregation)
        daily_data = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            day_metrics = play_logs.filter(
                played_at__range=(day_start, day_end)
            ).aggregate(
                plays=Count('id'),
                revenue=Sum('royalty_amount') or Decimal('0')
            )
            
            daily_data.append({
                'date': current_date.isoformat(),
                'plays': day_metrics['plays'],
                'revenue': float(day_metrics['revenue'])
            })
            current_date += timedelta(days=1)
        
        # Station performance
        station_performance = play_logs.values(
            'station__name', 'station__station_id', 'station__station_class'
        ).annotate(
            play_count=Count('id'),
            revenue=Sum('royalty_amount') or Decimal('0'),
            avg_confidence=Avg('avg_confidence_score') or Decimal('0')
        ).order_by('-play_count')[:15]
        
        # Trend analysis (compare with previous period)
        previous_start = start_date - (end_date - start_date)
        previous_end = start_date
        
        previous_metrics = PlayLog.objects.filter(
            track__track_id__in=track_ids,
            played_at__range=(previous_start, previous_end),
            active=True
        ).aggregate(
            total_plays=Count('id'),
            total_revenue=Sum('royalty_amount') or Decimal('0')
        )
        
        # Calculate trends
        plays_trend = self._calculate_trend(
            basic_metrics['total_plays'], 
            previous_metrics['total_plays']
        )
        revenue_trend = self._calculate_trend(
            float(basic_metrics['total_revenue']), 
            float(previous_metrics['total_revenue'])
        )
        
        analytics_data = {
            'artist_info': {
                'artist_id': artist_id,
                'stage_name': artist.stage_name,
                'total_tracks': tracks.count(),
                'verified': artist.verified
            },
            'summary': {
                'total_plays': basic_metrics['total_plays'],
                'total_revenue': float(basic_metrics['total_revenue']),
                'avg_confidence_score': float(basic_metrics['avg_confidence']),
                'unique_stations': basic_metrics['unique_stations'],
                'plays_trend': plays_trend,
                'revenue_trend': revenue_trend
            },
            'top_tracks': list(top_tracks),
            'geographic_distribution': list(geographic_data),
            'daily_trends': daily_data,
            'station_performance': list(station_performance),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'generated_at': timezone.now().isoformat()
        }
        
        # Cache the results
        self.set_cached_data(cache_key, analytics_data, timeout=1800)  # 30 minutes
        
        return analytics_data
    
    def get_publisher_analytics(self, publisher_id: int, date_range: Tuple[datetime, datetime]) -> Dict:
        """Get comprehensive analytics for a publisher"""
        start_date, end_date = date_range
        cache_key = self.generate_cache_key(
            'publisher_analytics',
            publisher_id=publisher_id,
            start=start_date.date(),
            end=end_date.date()
        )
        
        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        try:
            publisher = PublisherProfile.objects.get(id=publisher_id)
            artists = Artist.objects.filter(publisher=publisher, active=True)
            artist_ids = list(artists.values_list('artist_id', flat=True))
        except PublisherProfile.DoesNotExist:
            return {}
        
        # Get all tracks for publisher's artists
        tracks = Track.objects.filter(artist__artist_id__in=artist_ids, active=True)
        track_ids = list(tracks.values_list('track_id', flat=True))
        
        # Base queryset
        play_logs = PlayLog.objects.filter(
            track__track_id__in=track_ids,
            played_at__range=(start_date, end_date),
            active=True
        )
        
        # Portfolio overview
        portfolio_metrics = play_logs.aggregate(
            total_plays=Count('id'),
            total_revenue=Sum('royalty_amount') or Decimal('0'),
            unique_stations=Count('station', distinct=True),
            unique_tracks=Count('track', distinct=True)
        )
        
        # Artist performance comparison
        artist_performance = []
        for artist in artists:
            artist_tracks = tracks.filter(artist=artist)
            artist_track_ids = list(artist_tracks.values_list('track_id', flat=True))
            
            artist_metrics = play_logs.filter(
                track__track_id__in=artist_track_ids
            ).aggregate(
                plays=Count('id'),
                revenue=Sum('royalty_amount') or Decimal('0'),
                tracks_count=Count('track', distinct=True)
            )
            
            artist_performance.append({
                'artist_id': artist.artist_id,
                'stage_name': artist.stage_name,
                'plays': artist_metrics['plays'],
                'revenue': float(artist_metrics['revenue']),
                'tracks_count': artist_metrics['tracks_count'],
                'avg_revenue_per_track': float(artist_metrics['revenue']) / max(artist_metrics['tracks_count'], 1)
            })
        
        # Sort by revenue
        artist_performance.sort(key=lambda x: x['revenue'], reverse=True)
        
        # Revenue distribution by artist
        revenue_distribution = play_logs.values(
            'track__artist__stage_name', 'track__artist__artist_id'
        ).annotate(
            revenue=Sum('royalty_amount') or Decimal('0'),
            plays=Count('id')
        ).order_by('-revenue')[:10]
        
        # Monthly trends
        monthly_data = []
        current_month = start_date.replace(day=1)
        while current_month <= end_date:
            next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
            month_end = min(next_month - timedelta(days=1), end_date)
            
            month_metrics = play_logs.filter(
                played_at__range=(current_month, month_end)
            ).aggregate(
                plays=Count('id'),
                revenue=Sum('royalty_amount') or Decimal('0'),
                unique_artists=Count('track__artist', distinct=True)
            )
            
            monthly_data.append({
                'month': current_month.strftime('%Y-%m'),
                'plays': month_metrics['plays'],
                'revenue': float(month_metrics['revenue']),
                'unique_artists': month_metrics['unique_artists']
            })
            
            current_month = next_month
            if current_month > end_date:
                break
        
        analytics_data = {
            'publisher_info': {
                'publisher_id': publisher_id,
                'company_name': publisher.company_name,
                'total_artists': artists.count(),
                'total_tracks': tracks.count()
            },
            'portfolio_summary': {
                'total_plays': portfolio_metrics['total_plays'],
                'total_revenue': float(portfolio_metrics['total_revenue']),
                'unique_stations': portfolio_metrics['unique_stations'],
                'unique_tracks': portfolio_metrics['unique_tracks'],
                'avg_revenue_per_play': float(portfolio_metrics['total_revenue']) / max(portfolio_metrics['total_plays'], 1)
            },
            'artist_performance': artist_performance,
            'revenue_distribution': list(revenue_distribution),
            'monthly_trends': monthly_data,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'generated_at': timezone.now().isoformat()
        }
        
        # Cache the results
        self.set_cached_data(cache_key, analytics_data, timeout=1800)
        
        return analytics_data
    
    def get_station_analytics(self, station_id: str, date_range: Tuple[datetime, datetime]) -> Dict:
        """Get comprehensive analytics for a station"""
        start_date, end_date = date_range
        cache_key = self.generate_cache_key(
            'station_analytics',
            station_id=station_id,
            start=start_date.date(),
            end=end_date.date()
        )
        
        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        try:
            station = Station.objects.get(station_id=station_id)
        except Station.DoesNotExist:
            return {}
        
        # Play logs for this station
        play_logs = PlayLog.objects.filter(
            station=station,
            played_at__range=(start_date, end_date),
            active=True
        )
        
        # Detection data
        detections = AudioDetection.objects.filter(
            station=station,
            detected_at__range=(start_date, end_date)
        )
        
        # Basic metrics
        basic_metrics = play_logs.aggregate(
            total_plays=Count('id'),
            total_revenue_generated=Sum('royalty_amount') or Decimal('0'),
            avg_confidence=Avg('avg_confidence_score') or Decimal('0'),
            unique_tracks=Count('track', distinct=True),
            unique_artists=Count('track__artist', distinct=True)
        )
        
        # Detection accuracy metrics
        detection_metrics = detections.aggregate(
            total_detections=Count('id'),
            high_confidence_detections=Count('id', filter=Q(confidence_score__gte=0.8)),
            avg_detection_confidence=Avg('confidence_score') or Decimal('0'),
            local_detections=Count('id', filter=Q(detection_source='local')),
            acrcloud_detections=Count('id', filter=Q(detection_source='acrcloud'))
        )
        
        # Calculate detection accuracy rate
        detection_accuracy = 0
        if detection_metrics['total_detections'] > 0:
            detection_accuracy = (detection_metrics['high_confidence_detections'] / 
                                detection_metrics['total_detections']) * 100
        
        # Top played tracks
        top_tracks = play_logs.values(
            'track__title', 'track__artist__stage_name', 'track__track_id'
        ).annotate(
            play_count=Count('id'),
            avg_confidence=Avg('avg_confidence_score') or Decimal('0')
        ).order_by('-play_count')[:15]
        
        # Hourly distribution (to see peak hours)
        hourly_distribution = []
        for hour in range(24):
            hour_plays = play_logs.filter(
                played_at__hour=hour
            ).count()
            hourly_distribution.append({
                'hour': hour,
                'plays': hour_plays
            })
        
        # Daily compliance (submission vs detection)
        daily_compliance = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            day_plays = play_logs.filter(played_at__range=(day_start, day_end)).count()
            day_detections = detections.filter(detected_at__range=(day_start, day_end)).count()
            
            compliance_rate = 0
            if day_detections > 0:
                compliance_rate = (day_plays / day_detections) * 100
            
            daily_compliance.append({
                'date': current_date.isoformat(),
                'submitted_plays': day_plays,
                'detected_plays': day_detections,
                'compliance_rate': min(compliance_rate, 100)  # Cap at 100%
            })
            
            current_date += timedelta(days=1)
        
        # Detection source breakdown
        detection_source_breakdown = {
            'local': detection_metrics['local_detections'],
            'acrcloud': detection_metrics['acrcloud_detections'],
            'total': detection_metrics['total_detections']
        }
        
        analytics_data = {
            'station_info': {
                'station_id': station_id,
                'name': station.name,
                'station_class': station.station_class,
                'station_type': station.station_type,
                'region': station.region,
                'city': station.city
            },
            'summary': {
                'total_plays': basic_metrics['total_plays'],
                'total_revenue_generated': float(basic_metrics['total_revenue_generated']),
                'avg_confidence_score': float(basic_metrics['avg_confidence']),
                'unique_tracks': basic_metrics['unique_tracks'],
                'unique_artists': basic_metrics['unique_artists'],
                'detection_accuracy_rate': round(detection_accuracy, 2)
            },
            'detection_metrics': {
                'total_detections': detection_metrics['total_detections'],
                'high_confidence_detections': detection_metrics['high_confidence_detections'],
                'avg_detection_confidence': float(detection_metrics['avg_detection_confidence']),
                'detection_source_breakdown': detection_source_breakdown
            },
            'top_tracks': list(top_tracks),
            'hourly_distribution': hourly_distribution,
            'daily_compliance': daily_compliance,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'generated_at': timezone.now().isoformat()
        }
        
        # Cache the results
        self.set_cached_data(cache_key, analytics_data, timeout=1800)
        
        return analytics_data
    
    def get_admin_analytics(self, date_range: Tuple[datetime, datetime]) -> Dict:
        """Get platform-wide analytics for administrators"""
        start_date, end_date = date_range
        cache_key = self.generate_cache_key(
            'admin_analytics',
            start=start_date.date(),
            end=end_date.date()
        )
        
        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        # Platform-wide metrics
        platform_metrics = {
            'total_users': User.objects.filter(is_active=True).count(),
            'total_artists': Artist.objects.filter(active=True).count(),
            'total_stations': Station.objects.filter(active=True).count(),
            'total_publishers': PublisherProfile.objects.filter(active=True).count(),
            'total_tracks': Track.objects.filter(active=True).count()
        }
        
        # Play and revenue metrics for date range
        play_metrics = PlayLog.objects.filter(
            played_at__range=(start_date, end_date),
            active=True
        ).aggregate(
            total_plays=Count('id'),
            total_revenue=Sum('royalty_amount') or Decimal('0'),
            unique_tracks=Count('track', distinct=True),
            unique_stations=Count('station', distinct=True)
        )
        
        # Detection metrics
        detection_metrics = AudioDetection.objects.filter(
            detected_at__range=(start_date, end_date)
        ).aggregate(
            total_detections=Count('id'),
            successful_detections=Count('id', filter=Q(processing_status='completed')),
            failed_detections=Count('id', filter=Q(processing_status='failed')),
            avg_confidence=Avg('confidence_score') or Decimal('0')
        )
        
        # System health indicators
        processing_success_rate = 0
        if detection_metrics['total_detections'] > 0:
            processing_success_rate = (detection_metrics['successful_detections'] / 
                                     detection_metrics['total_detections']) * 100
        
        # Top performing regions
        regional_performance = PlayLog.objects.filter(
            played_at__range=(start_date, end_date),
            active=True
        ).values(
            'station__region'
        ).annotate(
            plays=Count('id'),
            revenue=Sum('royalty_amount') or Decimal('0'),
            unique_stations=Count('station', distinct=True)
        ).order_by('-plays')[:10]
        
        # Revenue distribution by user type
        revenue_by_type = RoyaltyDistribution.objects.filter(
            calculated_at__range=(start_date, end_date),
            status='paid'
        ).values(
            'recipient_type'
        ).annotate(
            total_amount=Sum('net_amount') or Decimal('0'),
            count=Count('id')
        )
        
        # Daily system activity
        daily_activity = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            day_metrics = {
                'date': current_date.isoformat(),
                'plays': PlayLog.objects.filter(
                    played_at__range=(day_start, day_end), active=True
                ).count(),
                'detections': AudioDetection.objects.filter(
                    detected_at__range=(day_start, day_end)
                ).count(),
                'new_users': User.objects.filter(
                    date_joined__range=(day_start, day_end)
                ).count(),
                'new_tracks': Track.objects.filter(
                    created_at__range=(day_start, day_end), active=True
                ).count()
            }
            
            daily_activity.append(day_metrics)
            current_date += timedelta(days=1)
        
        analytics_data = {
            'platform_overview': platform_metrics,
            'period_summary': {
                'total_plays': play_metrics['total_plays'],
                'total_revenue': float(play_metrics['total_revenue']),
                'unique_tracks_played': play_metrics['unique_tracks'],
                'active_stations': play_metrics['unique_stations'],
                'processing_success_rate': round(processing_success_rate, 2)
            },
            'detection_health': {
                'total_detections': detection_metrics['total_detections'],
                'successful_detections': detection_metrics['successful_detections'],
                'failed_detections': detection_metrics['failed_detections'],
                'avg_confidence_score': float(detection_metrics['avg_confidence'])
            },
            'regional_performance': list(regional_performance),
            'revenue_distribution': list(revenue_by_type),
            'daily_activity': daily_activity,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'generated_at': timezone.now().isoformat()
        }
        
        # Cache the results
        self.set_cached_data(cache_key, analytics_data, timeout=900)  # 15 minutes
        
        return analytics_data
    
    def update_realtime_metric(self, metric_name: str, value: Decimal, **dimensions):
        """Update a real-time metric"""
        RealtimeMetric.objects.create(
            metric_name=metric_name,
            value=value,
            station_id=dimensions.get('station_id'),
            artist_id=dimensions.get('artist_id'),
            metadata=dimensions.get('metadata', {})
        )
        
        # Also update Redis for immediate access
        redis_key = f"{self.cache_prefix}realtime:{metric_name}"
        if dimensions.get('station_id'):
            redis_key += f":station:{dimensions['station_id']}"
        if dimensions.get('artist_id'):
            redis_key += f":artist:{dimensions['artist_id']}"
        
        metric_data = {
            'value': float(value),
            'timestamp': timezone.now().isoformat(),
            'metadata': dimensions.get('metadata', {})
        }
        
        self.set_cached_data(redis_key, metric_data, timeout=300)  # 5 minutes
    
    def get_realtime_metrics(self, metric_names: List[str], **filters) -> Dict:
        """Get current real-time metrics"""
        metrics = {}
        
        for metric_name in metric_names:
            redis_key = f"{self.cache_prefix}realtime:{metric_name}"
            if filters.get('station_id'):
                redis_key += f":station:{filters['station_id']}"
            if filters.get('artist_id'):
                redis_key += f":artist:{filters['artist_id']}"
            
            cached_metric = self.get_cached_data(redis_key)
            if cached_metric:
                metrics[metric_name] = cached_metric
            else:
                # Fallback to database
                latest_metric = RealtimeMetric.objects.filter(
                    metric_name=metric_name,
                    **{k: v for k, v in filters.items() if v is not None}
                ).order_by('-timestamp').first()
                
                if latest_metric:
                    metrics[metric_name] = {
                        'value': float(latest_metric.value),
                        'timestamp': latest_metric.timestamp.isoformat(),
                        'metadata': latest_metric.metadata
                    }
        
        return metrics
    
    def _calculate_trend(self, current_value: float, previous_value: float) -> Dict:
        """Calculate trend percentage and direction"""
        if previous_value == 0:
            if current_value > 0:
                return {'percentage': 100, 'direction': 'up', 'status': 'positive'}
            else:
                return {'percentage': 0, 'direction': 'neutral', 'status': 'neutral'}
        
        percentage_change = ((current_value - previous_value) / previous_value) * 100
        
        return {
            'percentage': round(abs(percentage_change), 2),
            'direction': 'up' if percentage_change > 0 else 'down' if percentage_change < 0 else 'neutral',
            'status': 'positive' if percentage_change > 0 else 'negative' if percentage_change < 0 else 'neutral'
        }
    
    def create_analytics_snapshot(self, snapshot_type: str, metric_type: str, 
                                period_start: datetime, period_end: datetime,
                                **dimensions):
        """Create time-series snapshots for efficient historical queries"""
        # This would be called by a scheduled task to pre-aggregate data
        pass
    
    def cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        try:
            # Clean up Redis cache
            expired_keys = []
            for key in self.redis_client.scan_iter(match=f"{self.cache_prefix}*"):
                ttl = self.redis_client.ttl(key)
                if ttl == -1:  # No expiration set
                    continue
                if ttl <= 0:  # Expired
                    expired_keys.append(key)
            
            if expired_keys:
                self.redis_client.delete(*expired_keys)
            
            # Clean up database cache entries
            AnalyticsCache.objects.filter(expires_at__lt=timezone.now()).delete()
            
        except redis.RedisError:
            pass


# Singleton instance
analytics_aggregator = AnalyticsAggregator()