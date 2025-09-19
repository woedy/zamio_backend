"""
Django management command to manage Redis cache operations including
warming, monitoring, and maintenance.
"""

from django.core.management.base import BaseCommand, CommandError
from core.caching_service import (
    CacheService, AnalyticsCacheService, UserCacheService, 
    TrackCacheService, DetectionCacheService, RoyaltyCacheService,
    CacheWarmer, CacheMonitor
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage Redis cache operations for performance optimization'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='Pre-warm cache with frequently accessed data',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear all cache data',
        )
        parser.add_argument(
            '--cache-stats',
            action='store_true',
            help='Display cache usage statistics',
        )
        parser.add_argument(
            '--list-keys',
            action='store_true',
            help='List all cache keys (for debugging)',
        )
        parser.add_argument(
            '--invalidate-pattern',
            type=str,
            help='Invalidate cache keys matching pattern',
        )
        parser.add_argument(
            '--warm-analytics',
            action='store_true',
            help='Warm analytics cache specifically',
        )
        parser.add_argument(
            '--warm-users',
            action='store_true',
            help='Warm user cache specifically',
        )
        parser.add_argument(
            '--warm-tracks',
            action='store_true',
            help='Warm track cache specifically',
        )
        parser.add_argument(
            '--test-cache',
            action='store_true',
            help='Test cache operations',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting cache management operations...')
        )
        
        try:
            if options['warm_cache']:
                self._warm_all_caches()
            
            if options['warm_analytics']:
                self._warm_analytics_cache()
            
            if options['warm_users']:
                self._warm_user_cache()
            
            if options['warm_tracks']:
                self._warm_track_cache()
            
            if options['clear_cache']:
                self._clear_cache()
            
            if options['cache_stats']:
                self._show_cache_stats()
            
            if options['list_keys']:
                self._list_cache_keys()
            
            if options['invalidate_pattern']:
                self._invalidate_pattern(options['invalidate_pattern'])
            
            if options['test_cache']:
                self._test_cache_operations()
            
            self.stdout.write(
                self.style.SUCCESS('Cache management operations completed!')
            )
            
        except Exception as e:
            logger.error(f"Cache management failed: {e}")
            raise CommandError(f'Cache management failed: {e}')
    
    def _warm_all_caches(self):
        """Warm all cache types"""
        self.stdout.write('Warming all caches...')
        
        try:
            # Warm user caches
            CacheWarmer.warm_user_caches()
            self.stdout.write(self.style.SUCCESS('✓ Warmed user caches'))
            
            # Warm analytics caches
            CacheWarmer.warm_analytics_caches()
            self.stdout.write(self.style.SUCCESS('✓ Warmed analytics caches'))
            
            # Warm track caches
            CacheWarmer.warm_track_caches()
            self.stdout.write(self.style.SUCCESS('✓ Warmed track caches'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to warm caches: {e}'))
            raise
    
    def _warm_analytics_cache(self):
        """Warm analytics cache specifically"""
        self.stdout.write('Warming analytics cache...')
        
        try:
            CacheWarmer.warm_analytics_caches()
            self.stdout.write(self.style.SUCCESS('✓ Warmed analytics cache'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to warm analytics cache: {e}'))
            raise
    
    def _warm_user_cache(self):
        """Warm user cache specifically"""
        self.stdout.write('Warming user cache...')
        
        try:
            CacheWarmer.warm_user_caches()
            self.stdout.write(self.style.SUCCESS('✓ Warmed user cache'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to warm user cache: {e}'))
            raise
    
    def _warm_track_cache(self):
        """Warm track cache specifically"""
        self.stdout.write('Warming track cache...')
        
        try:
            CacheWarmer.warm_track_caches()
            self.stdout.write(self.style.SUCCESS('✓ Warmed track cache'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to warm track cache: {e}'))
            raise
    
    def _clear_cache(self):
        """Clear all cache data"""
        self.stdout.write(self.style.WARNING('Clearing all cache data...'))
        
        # Ask for confirmation
        confirm = input('Are you sure you want to clear all cache? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write('Cache clear cancelled.')
            return
        
        try:
            success = CacheMonitor.clear_all_cache()
            if success:
                self.stdout.write(self.style.SUCCESS('✓ Cleared all cache data'))
            else:
                self.stdout.write(self.style.ERROR('Failed to clear cache'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to clear cache: {e}'))
            raise
    
    def _show_cache_stats(self):
        """Display cache usage statistics"""
        self.stdout.write('Cache Usage Statistics:')
        self.stdout.write('=' * 40)
        
        try:
            stats = CacheMonitor.get_cache_stats()
            
            if stats:
                self.stdout.write(f"Connected Clients: {stats.get('connected_clients', 'N/A')}")
                self.stdout.write(f"Used Memory: {stats.get('used_memory', 'N/A')}")
                self.stdout.write(f"Keyspace Hits: {stats.get('keyspace_hits', 'N/A')}")
                self.stdout.write(f"Keyspace Misses: {stats.get('keyspace_misses', 'N/A')}")
                self.stdout.write(f"Hit Rate: {stats.get('hit_rate', 0):.2f}%")
                self.stdout.write(f"Total Commands: {stats.get('total_commands_processed', 'N/A')}")
            else:
                self.stdout.write('No cache statistics available (requires Redis)')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get cache stats: {e}'))
    
    def _list_cache_keys(self):
        """List all cache keys for debugging"""
        self.stdout.write('Cache Keys:')
        self.stdout.write('=' * 20)
        
        try:
            keys = CacheMonitor.get_cache_keys_by_pattern()
            
            if keys:
                # Group keys by prefix
                key_groups = {}
                for key in keys:
                    parts = key.split(':')
                    if len(parts) >= 2:
                        prefix = parts[1]  # Skip 'zamio' prefix
                        if prefix not in key_groups:
                            key_groups[prefix] = []
                        key_groups[prefix].append(key)
                
                for prefix, prefix_keys in key_groups.items():
                    self.stdout.write(f"\n{prefix.upper()} ({len(prefix_keys)} keys):")
                    for key in prefix_keys[:10]:  # Show first 10 keys
                        self.stdout.write(f"  {key}")
                    if len(prefix_keys) > 10:
                        self.stdout.write(f"  ... and {len(prefix_keys) - 10} more")
            else:
                self.stdout.write('No cache keys found')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to list cache keys: {e}'))
    
    def _invalidate_pattern(self, pattern):
        """Invalidate cache keys matching pattern"""
        self.stdout.write(f'Invalidating cache keys matching pattern: {pattern}')
        
        try:
            success = CacheService.invalidate_pattern(pattern)
            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Invalidated keys matching: {pattern}'))
            else:
                self.stdout.write(self.style.ERROR(f'Failed to invalidate pattern: {pattern}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to invalidate pattern: {e}'))
            raise
    
    def _test_cache_operations(self):
        """Test cache operations to ensure they're working"""
        self.stdout.write('Testing cache operations...')
        
        try:
            # Test basic cache operations
            test_key = 'test_cache_operation'
            test_data = {'message': 'Hello, Cache!', 'timestamp': '2024-01-01'}
            
            # Test set operation
            success = CacheService.set('test', test_key, test_data, 'short')
            if success:
                self.stdout.write('✓ Cache SET operation successful')
            else:
                self.stdout.write(self.style.ERROR('✗ Cache SET operation failed'))
                return
            
            # Test get operation
            cached_data = CacheService.get('test', test_key)
            if cached_data == test_data:
                self.stdout.write('✓ Cache GET operation successful')
            else:
                self.stdout.write(self.style.ERROR('✗ Cache GET operation failed'))
                return
            
            # Test delete operation
            success = CacheService.delete('test', test_key)
            if success:
                self.stdout.write('✓ Cache DELETE operation successful')
            else:
                self.stdout.write(self.style.ERROR('✗ Cache DELETE operation failed'))
                return
            
            # Test that data is actually deleted
            cached_data = CacheService.get('test', test_key)
            if cached_data is None:
                self.stdout.write('✓ Cache deletion verified')
            else:
                self.stdout.write(self.style.ERROR('✗ Cache deletion verification failed'))
                return
            
            # Test specialized cache services
            self._test_specialized_caches()
            
            self.stdout.write(self.style.SUCCESS('All cache operations working correctly!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Cache test failed: {e}'))
            raise
    
    def _test_specialized_caches(self):
        """Test specialized cache services"""
        # Test analytics cache
        test_analytics = {'total_plays': 100, 'total_earnings': 50.0}
        AnalyticsCacheService.cache_station_analytics(1, '2024-01-01', test_analytics)
        cached_analytics = AnalyticsCacheService.get_station_analytics(1, '2024-01-01')
        
        if cached_analytics == test_analytics:
            self.stdout.write('✓ Analytics cache service working')
        else:
            self.stdout.write(self.style.ERROR('✗ Analytics cache service failed'))
        
        # Test user cache
        test_profile = {'user_id': 1, 'email': 'test@example.com'}
        UserCacheService.cache_user_profile(1, test_profile)
        cached_profile = UserCacheService.get_user_profile(1)
        
        if cached_profile == test_profile:
            self.stdout.write('✓ User cache service working')
        else:
            self.stdout.write(self.style.ERROR('✗ User cache service failed'))
        
        # Clean up test data
        AnalyticsCacheService.delete('analytics', 'station_analytics:1:2024-01-01')
        UserCacheService.delete('user', 'profile:1')
    
    def _show_cache_recommendations(self):
        """Show cache optimization recommendations"""
        self.stdout.write('\nCache Optimization Recommendations:')
        self.stdout.write('=' * 45)
        
        recommendations = [
            "1. Warm cache during off-peak hours: python manage.py manage_cache --warm-cache",
            "2. Monitor cache hit rates regularly: python manage.py manage_cache --cache-stats",
            "3. Set up automated cache warming for critical data",
            "4. Use appropriate cache timeouts based on data volatility",
            "5. Implement cache invalidation on data updates",
            "6. Consider Redis clustering for high availability",
            "7. Monitor Redis memory usage and set appropriate limits",
            "8. Use cache compression for large data sets",
        ]
        
        for recommendation in recommendations:
            self.stdout.write(f'  {recommendation}')
        
        self.stdout.write('\nCache Key Patterns:')
        self.stdout.write('  - zamio:analytics:* - Analytics data')
        self.stdout.write('  - zamio:user:* - User profiles and permissions')
        self.stdout.write('  - zamio:track:* - Track metadata and fingerprints')
        self.stdout.write('  - zamio:detection:* - Audio detection results')
        self.stdout.write('  - zamio:royalty:* - Royalty calculations and summaries')