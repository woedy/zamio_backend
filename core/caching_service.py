"""
Caching service for ZamIO platform to improve performance by caching
frequently accessed data using Redis.
"""

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db.models import QuerySet
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


class CacheService:
    """Centralized caching service for frequently accessed data"""
    
    # Cache key prefixes for different data types
    PREFIXES = {
        'user': 'user',
        'artist': 'artist',
        'station': 'station',
        'track': 'track',
        'playlog': 'playlog',
        'analytics': 'analytics',
        'detection': 'detection',
        'royalty': 'royalty',
        'fingerprint': 'fingerprint',
    }
    
    # Default cache timeouts (in seconds)
    TIMEOUTS = {
        'short': 300,      # 5 minutes
        'medium': 1800,    # 30 minutes
        'long': 3600,      # 1 hour
        'daily': 86400,    # 24 hours
        'weekly': 604800,  # 7 days
    }
    
    @classmethod
    def _make_key(cls, prefix: str, identifier: str) -> str:
        """Create a standardized cache key"""
        return f"zamio:{prefix}:{identifier}"
    
    @classmethod
    def _serialize_data(cls, data: Any) -> str:
        """Serialize data for caching"""
        if isinstance(data, QuerySet):
            return serialize('json', data)
        return json.dumps(data, cls=DjangoJSONEncoder)
    
    @classmethod
    def _deserialize_data(cls, data: str) -> Any:
        """Deserialize cached data"""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data
    
    @classmethod
    def set(cls, prefix: str, identifier: str, data: Any, timeout: str = 'medium') -> bool:
        """Set data in cache with specified timeout"""
        try:
            key = cls._make_key(prefix, identifier)
            serialized_data = cls._serialize_data(data)
            timeout_seconds = cls.TIMEOUTS.get(timeout, cls.TIMEOUTS['medium'])
            
            cache.set(key, serialized_data, timeout_seconds)
            logger.debug(f"Cached data with key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache data: {e}")
            return False
    
    @classmethod
    def get(cls, prefix: str, identifier: str) -> Optional[Any]:
        """Get data from cache"""
        try:
            key = cls._make_key(prefix, identifier)
            cached_data = cache.get(key)
            
            if cached_data is not None:
                logger.debug(f"Cache hit for key: {key}")
                return cls._deserialize_data(cached_data)
            
            logger.debug(f"Cache miss for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Failed to get cached data: {e}")
            return None
    
    @classmethod
    def delete(cls, prefix: str, identifier: str) -> bool:
        """Delete data from cache"""
        try:
            key = cls._make_key(prefix, identifier)
            cache.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete cached data: {e}")
            return False
    
    @classmethod
    def invalidate_pattern(cls, pattern: str) -> bool:
        """Invalidate cache keys matching a pattern"""
        try:
            # This requires django-redis backend
            cache.delete_pattern(f"zamio:{pattern}*")
            logger.info(f"Invalidated cache pattern: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern: {e}")
            return False


class AnalyticsCacheService(CacheService):
    """Specialized caching service for analytics data"""
    
    @classmethod
    def cache_station_analytics(cls, station_id: int, date_range: str, data: Dict) -> bool:
        """Cache station analytics data"""
        key = f"station_analytics:{station_id}:{date_range}"
        return cls.set('analytics', key, data, 'long')
    
    @classmethod
    def get_station_analytics(cls, station_id: int, date_range: str) -> Optional[Dict]:
        """Get cached station analytics data"""
        key = f"station_analytics:{station_id}:{date_range}"
        return cls.get('analytics', key)
    
    @classmethod
    def cache_artist_analytics(cls, artist_id: int, date_range: str, data: Dict) -> bool:
        """Cache artist analytics data"""
        key = f"artist_analytics:{artist_id}:{date_range}"
        return cls.set('analytics', key, data, 'long')
    
    @classmethod
    def get_artist_analytics(cls, artist_id: int, date_range: str) -> Optional[Dict]:
        """Get cached artist analytics data"""
        key = f"artist_analytics:{artist_id}:{date_range}"
        return cls.get('analytics', key)
    
    @classmethod
    def cache_platform_analytics(cls, date_range: str, data: Dict) -> bool:
        """Cache platform-wide analytics data"""
        key = f"platform_analytics:{date_range}"
        return cls.set('analytics', key, data, 'medium')
    
    @classmethod
    def get_platform_analytics(cls, date_range: str) -> Optional[Dict]:
        """Get cached platform analytics data"""
        key = f"platform_analytics:{date_range}"
        return cls.get('analytics', key)
    
    @classmethod
    def invalidate_analytics(cls, entity_type: str = None, entity_id: int = None):
        """Invalidate analytics cache for specific entity or all analytics"""
        if entity_type and entity_id:
            pattern = f"analytics:{entity_type}_analytics:{entity_id}"
        else:
            pattern = "analytics"
        
        cls.invalidate_pattern(pattern)


class UserCacheService(CacheService):
    """Specialized caching service for user data"""
    
    @classmethod
    def cache_user_profile(cls, user_id: int, profile_data: Dict) -> bool:
        """Cache user profile data"""
        return cls.set('user', f"profile:{user_id}", profile_data, 'long')
    
    @classmethod
    def get_user_profile(cls, user_id: int) -> Optional[Dict]:
        """Get cached user profile data"""
        return cls.get('user', f"profile:{user_id}")
    
    @classmethod
    def cache_user_permissions(cls, user_id: int, permissions: List[str]) -> bool:
        """Cache user permissions"""
        return cls.set('user', f"permissions:{user_id}", permissions, 'medium')
    
    @classmethod
    def get_user_permissions(cls, user_id: int) -> Optional[List[str]]:
        """Get cached user permissions"""
        return cls.get('user', f"permissions:{user_id}")
    
    @classmethod
    def invalidate_user_cache(cls, user_id: int):
        """Invalidate all cache for a specific user"""
        cls.delete('user', f"profile:{user_id}")
        cls.delete('user', f"permissions:{user_id}")


class TrackCacheService(CacheService):
    """Specialized caching service for track and music data"""
    
    @classmethod
    def cache_track_fingerprints(cls, track_id: int, fingerprints: List[Dict]) -> bool:
        """Cache track fingerprint data"""
        return cls.set('fingerprint', f"track:{track_id}", fingerprints, 'daily')
    
    @classmethod
    def get_track_fingerprints(cls, track_id: int) -> Optional[List[Dict]]:
        """Get cached track fingerprint data"""
        return cls.get('fingerprint', f"track:{track_id}")
    
    @classmethod
    def cache_artist_tracks(cls, artist_id: int, tracks: List[Dict]) -> bool:
        """Cache artist's tracks"""
        return cls.set('track', f"artist:{artist_id}", tracks, 'medium')
    
    @classmethod
    def get_artist_tracks(cls, artist_id: int) -> Optional[List[Dict]]:
        """Get cached artist tracks"""
        return cls.get('track', f"artist:{artist_id}")
    
    @classmethod
    def cache_track_metadata(cls, track_id: int, metadata: Dict) -> bool:
        """Cache track metadata"""
        return cls.set('track', f"metadata:{track_id}", metadata, 'long')
    
    @classmethod
    def get_track_metadata(cls, track_id: int) -> Optional[Dict]:
        """Get cached track metadata"""
        return cls.get('track', f"metadata:{track_id}")
    
    @classmethod
    def invalidate_track_cache(cls, track_id: int):
        """Invalidate all cache for a specific track"""
        cls.delete('track', f"metadata:{track_id}")
        cls.delete('fingerprint', f"track:{track_id}")


class DetectionCacheService(CacheService):
    """Specialized caching service for audio detection data"""
    
    @classmethod
    def cache_station_detections(cls, station_id: int, date: str, detections: List[Dict]) -> bool:
        """Cache station detection data for a specific date"""
        key = f"station:{station_id}:date:{date}"
        return cls.set('detection', key, detections, 'long')
    
    @classmethod
    def get_station_detections(cls, station_id: int, date: str) -> Optional[List[Dict]]:
        """Get cached station detection data"""
        key = f"station:{station_id}:date:{date}"
        return cls.get('detection', key)
    
    @classmethod
    def cache_detection_confidence_stats(cls, station_id: int, stats: Dict) -> bool:
        """Cache detection confidence statistics"""
        key = f"confidence_stats:{station_id}"
        return cls.set('detection', key, stats, 'medium')
    
    @classmethod
    def get_detection_confidence_stats(cls, station_id: int) -> Optional[Dict]:
        """Get cached detection confidence statistics"""
        key = f"confidence_stats:{station_id}"
        return cls.get('detection', key)


class RoyaltyCacheService(CacheService):
    """Specialized caching service for royalty data"""
    
    @classmethod
    def cache_royalty_cycle_data(cls, cycle_id: int, data: Dict) -> bool:
        """Cache royalty cycle data"""
        return cls.set('royalty', f"cycle:{cycle_id}", data, 'daily')
    
    @classmethod
    def get_royalty_cycle_data(cls, cycle_id: int) -> Optional[Dict]:
        """Get cached royalty cycle data"""
        return cls.get('royalty', f"cycle:{cycle_id}")
    
    @classmethod
    def cache_user_royalty_summary(cls, user_id: int, period: str, summary: Dict) -> bool:
        """Cache user royalty summary"""
        key = f"user_summary:{user_id}:{period}"
        return cls.set('royalty', key, summary, 'long')
    
    @classmethod
    def get_user_royalty_summary(cls, user_id: int, period: str) -> Optional[Dict]:
        """Get cached user royalty summary"""
        key = f"user_summary:{user_id}:{period}"
        return cls.get('royalty', key)
    
    @classmethod
    def cache_exchange_rates(cls, rates: Dict) -> bool:
        """Cache currency exchange rates"""
        return cls.set('royalty', 'exchange_rates', rates, 'long')
    
    @classmethod
    def get_exchange_rates(cls) -> Optional[Dict]:
        """Get cached exchange rates"""
        return cls.get('royalty', 'exchange_rates')


class CacheWarmer:
    """Service to pre-warm cache with frequently accessed data"""
    
    @staticmethod
    def warm_user_caches():
        """Pre-warm user-related caches"""
        from accounts.models import User
        
        # Cache active users' profiles
        active_users = User.objects.filter(is_active=True).select_related()
        for user in active_users[:100]:  # Limit to prevent overwhelming
            profile_data = {
                'user_id': user.user_id,
                'email': user.email,
                'user_type': user.user_type,
                'kyc_status': user.kyc_status,
                'profile_complete': user.profile_complete,
            }
            UserCacheService.cache_user_profile(user.id, profile_data)
        
        logger.info(f"Warmed cache for {active_users.count()} user profiles")
    
    @staticmethod
    def warm_analytics_caches():
        """Pre-warm analytics caches with recent data"""
        from datetime import datetime, timedelta
        
        # Warm platform analytics for last 7 days
        end_date = datetime.now().date()
        for i in range(7):
            date = end_date - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            # This would call actual analytics calculation
            # For now, we'll just create placeholder
            analytics_data = {
                'date': date_str,
                'total_plays': 0,
                'total_detections': 0,
                'total_royalties': 0,
                'cached_at': timezone.now().isoformat(),
            }
            
            AnalyticsCacheService.cache_platform_analytics(date_str, analytics_data)
        
        logger.info("Warmed analytics caches for last 7 days")
    
    @staticmethod
    def warm_track_caches():
        """Pre-warm track-related caches"""
        from artists.models import Track
        
        # Cache metadata for recently uploaded tracks
        recent_tracks = Track.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30),
            active=True
        ).select_related('artist')[:50]
        
        for track in recent_tracks:
            metadata = {
                'track_id': track.track_id,
                'title': track.title,
                'artist_name': track.artist.stage_name,
                'duration': str(track.duration) if track.duration else None,
                'isrc_code': track.isrc_code,
                'fingerprinted': track.fingerprinted,
            }
            TrackCacheService.cache_track_metadata(track.id, metadata)
        
        logger.info(f"Warmed cache for {recent_tracks.count()} track metadata")


class CacheInvalidator:
    """Service to handle cache invalidation on data changes"""
    
    @staticmethod
    def invalidate_on_user_update(user_id: int):
        """Invalidate user-related caches when user data changes"""
        UserCacheService.invalidate_user_cache(user_id)
        
        # Also invalidate analytics that might include this user
        AnalyticsCacheService.invalidate_pattern(f"analytics:*")
    
    @staticmethod
    def invalidate_on_track_update(track_id: int, artist_id: int = None):
        """Invalidate track-related caches when track data changes"""
        TrackCacheService.invalidate_track_cache(track_id)
        
        if artist_id:
            TrackCacheService.delete('track', f"artist:{artist_id}")
            AnalyticsCacheService.invalidate_pattern(f"analytics:artist_analytics:{artist_id}")
    
    @staticmethod
    def invalidate_on_playlog_create(station_id: int, track_id: int, artist_id: int):
        """Invalidate relevant caches when new play log is created"""
        # Invalidate analytics caches
        today = timezone.now().date().strftime('%Y-%m-%d')
        
        AnalyticsCacheService.delete('analytics', f"station_analytics:{station_id}:{today}")
        AnalyticsCacheService.delete('analytics', f"artist_analytics:{artist_id}:{today}")
        AnalyticsCacheService.delete('analytics', f"platform_analytics:{today}")
        
        # Invalidate detection caches
        DetectionCacheService.delete('detection', f"station:{station_id}:date:{today}")
    
    @staticmethod
    def invalidate_on_royalty_calculation(user_id: int, cycle_id: int = None):
        """Invalidate royalty-related caches when calculations are updated"""
        RoyaltyCacheService.invalidate_pattern(f"royalty:user_summary:{user_id}")
        
        if cycle_id:
            RoyaltyCacheService.delete('royalty', f"cycle:{cycle_id}")


# Cache monitoring and statistics
class CacheMonitor:
    """Monitor cache performance and usage statistics"""
    
    @staticmethod
    def get_cache_stats():
        """Get cache usage statistics"""
        try:
            # This requires django-redis backend
            from django_redis import get_redis_connection
            
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            stats = {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0B'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
            }
            
            # Calculate hit rate
            hits = stats['keyspace_hits']
            misses = stats['keyspace_misses']
            total = hits + misses
            
            if total > 0:
                stats['hit_rate'] = (hits / total) * 100
            else:
                stats['hit_rate'] = 0
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    @staticmethod
    def get_cache_keys_by_pattern(pattern: str = "zamio:*"):
        """Get cache keys matching pattern for debugging"""
        try:
            from django_redis import get_redis_connection
            
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys(pattern)
            
            return [key.decode('utf-8') for key in keys]
        except Exception as e:
            logger.error(f"Failed to get cache keys: {e}")
            return []
    
    @staticmethod
    def clear_all_cache():
        """Clear all cache (use with caution)"""
        try:
            cache.clear()
            logger.warning("Cleared all cache data")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False