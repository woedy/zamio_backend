"""
Database optimization utilities and index management for ZamIO platform.
This module provides database performance enhancements including proper indexing,
query optimization, and connection pooling configuration.
"""

from django.db import models, connection
from django.core.management.base import BaseCommand
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Database optimization utilities for improved performance"""
    
    @staticmethod
    def get_missing_indexes():
        """Identify missing database indexes for frequently queried fields"""
        missing_indexes = []
        
        # Common query patterns that need indexes
        index_recommendations = [
            # User model indexes
            ('accounts.User', ['email', 'user_type']),
            ('accounts.User', ['kyc_status', 'is_active']),
            ('accounts.User', ['last_activity']),
            ('accounts.User', ['user_type', 'is_active', 'kyc_status']),
            
            # Artist model indexes
            ('artists.Artist', ['user_id', 'self_published']),
            ('artists.Artist', ['publisher_id', 'royalty_collection_method']),
            ('artists.Artist', ['publisher_relationship_status', 'is_active']),
            ('artists.Artist', ['created_at', 'is_active']),
            
            # Track model indexes
            ('artists.Track', ['artist_id', 'status']),
            ('artists.Track', ['isrc_code']),
            ('artists.Track', ['fingerprinted', 'active']),
            ('artists.Track', ['publisher_id', 'status']),
            ('artists.Track', ['created_at', 'status']),
            
            # Contributor model indexes
            ('artists.Contributor', ['track_id', 'active']),
            ('artists.Contributor', ['user_id', 'role']),
            ('artists.Contributor', ['publisher_id', 'active']),
            
            # Station model indexes
            ('stations.Station', ['station_class', 'verification_status']),
            ('stations.Station', ['user_id', 'active']),
            ('stations.Station', ['city', 'region', 'country']),
            ('stations.Station', ['verification_status', 'active']),
            
            # PlayLog model indexes
            ('music_monitor.PlayLog', ['station_id', 'played_at']),
            ('music_monitor.PlayLog', ['track_id', 'played_at']),
            ('music_monitor.PlayLog', ['played_at', 'claimed']),
            ('music_monitor.PlayLog', ['station_id', 'track_id', 'played_at']),
            ('music_monitor.PlayLog', ['royalty_amount', 'claimed']),
            
            # AudioDetection model indexes
            ('music_monitor.AudioDetection', ['station_id', 'detected_at']),
            ('music_monitor.AudioDetection', ['detection_source', 'confidence_score']),
            ('music_monitor.AudioDetection', ['isrc', 'pro_affiliation']),
            ('music_monitor.AudioDetection', ['processing_status', 'retry_count']),
            ('music_monitor.AudioDetection', ['session_id', 'audio_timestamp']),
            
            # RoyaltyDistribution model indexes
            ('music_monitor.RoyaltyDistribution', ['recipient_id', 'status']),
            ('music_monitor.RoyaltyDistribution', ['play_log_id', 'recipient_type']),
            ('music_monitor.RoyaltyDistribution', ['status', 'calculated_at']),
            ('music_monitor.RoyaltyDistribution', ['external_pro_id', 'currency']),
            
            # Fingerprint model indexes
            ('artists.Fingerprint', ['hash', 'track_id']),
            ('artists.Fingerprint', ['processing_status', 'version']),
            ('artists.Fingerprint', ['track_id', 'algorithm', 'version']),
            
            # Royalty cycle and related indexes
            ('royalties.RoyaltyCycle', ['territory', 'status']),
            ('royalties.RoyaltyCycle', ['period_start', 'period_end']),
            ('royalties.UsageAttribution', ['territory', 'played_at']),
            ('royalties.RoyaltyLineItem', ['royalty_cycle_id', 'partner_id']),
            
            # Publisher model indexes
            ('publishers.PublisherProfile', ['user_id', 'verification_status']),
            ('publishers.PublisherProfile', ['territory', 'publisher_type']),
        ]
        
        return index_recommendations
    
    @staticmethod
    def create_composite_indexes():
        """Create composite indexes for complex queries"""
        with connection.cursor() as cursor:
            # Composite index for play log analytics queries
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_playlog_analytics 
                ON music_monitor_playlog (station_id, played_at, track_id, claimed)
            """)
            
            # Composite index for royalty distribution queries
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_royalty_distribution_analytics 
                ON music_monitor_royaltydistribution (recipient_id, status, calculated_at, currency)
            """)
            
            # Composite index for audio detection analytics
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_detection_analytics 
                ON music_monitor_audiodetection (station_id, detected_at, detection_source, confidence_score)
            """)
            
            # Composite index for user activity tracking
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity 
                ON accounts_user (user_type, is_active, last_activity, kyc_status)
            """)
            
            # Composite index for track management
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_management 
                ON artists_track (artist_id, status, fingerprinted, created_at)
            """)
            
            logger.info("Created composite database indexes for improved query performance")
    
    @staticmethod
    def optimize_frequent_queries():
        """Optimize frequently executed queries with proper indexing"""
        optimizations = [
            # Index for user authentication queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_auth ON accounts_user (email, is_active, user_type)",
            
            # Index for artist dashboard queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artist_dashboard ON artists_artist (user_id, self_published, active)",
            
            # Index for station monitoring queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_station_monitoring ON stations_station (verification_status, station_class, active)",
            
            # Index for royalty calculation queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_royalty_calc ON music_monitor_playlog (track_id, station_id, played_at, claimed)",
            
            # Index for analytics queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analytics_time ON music_monitor_playlog (played_at DESC, station_id, track_id)",
            
            # Index for detection processing
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detection_processing ON music_monitor_audiodetection (processing_status, retry_count, detected_at)",
            
            # Index for fingerprint matching
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fingerprint_match ON artists_fingerprint (hash, confidence_score, processing_status)",
        ]
        
        with connection.cursor() as cursor:
            for optimization in optimizations:
                try:
                    cursor.execute(optimization)
                    logger.info(f"Applied optimization: {optimization[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to apply optimization: {e}")
    
    @staticmethod
    def analyze_query_performance():
        """Analyze and log slow queries for optimization"""
        with connection.cursor() as cursor:
            # Enable query logging for analysis
            cursor.execute("SET log_statement = 'all'")
            cursor.execute("SET log_min_duration_statement = 1000")  # Log queries > 1 second
            
            # Get table statistics
            cursor.execute("""
                SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup
                FROM pg_stat_user_tables 
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
            """)
            
            stats = cursor.fetchall()
            logger.info(f"Database table statistics: {stats}")
    
    @staticmethod
    def setup_connection_pooling():
        """Configure database connection pooling for better performance"""
        # This would typically be configured in settings.py
        # but we can provide recommendations
        pooling_config = {
            'ENGINE': 'django.db.backends.postgresql',
            'OPTIONS': {
                'MAX_CONNS': 20,
                'MIN_CONNS': 5,
                'CONN_MAX_AGE': 600,  # 10 minutes
            }
        }
        
        logger.info(f"Recommended connection pooling config: {pooling_config}")
        return pooling_config


class QueryOptimizer:
    """Query optimization utilities for common database operations"""
    
    @staticmethod
    def optimize_playlog_queries():
        """Optimize PlayLog model queries for better performance"""
        from music_monitor.models import PlayLog
        
        # Use select_related for foreign key relationships
        def get_playlogs_with_relations(station_id=None, date_range=None):
            queryset = PlayLog.objects.select_related(
                'track', 'station', 'track__artist'
            ).prefetch_related(
                'track__contributors', 'royalty_distributions'
            )
            
            if station_id:
                queryset = queryset.filter(station_id=station_id)
            
            if date_range:
                queryset = queryset.filter(played_at__range=date_range)
            
            return queryset.order_by('-played_at')
        
        return get_playlogs_with_relations
    
    @staticmethod
    def optimize_analytics_queries():
        """Optimize analytics queries with proper aggregation"""
        from django.db.models import Count, Sum, Avg
        from music_monitor.models import PlayLog, AudioDetection
        
        def get_station_analytics(station_id, date_range):
            return PlayLog.objects.filter(
                station_id=station_id,
                played_at__range=date_range
            ).aggregate(
                total_plays=Count('id'),
                total_royalties=Sum('royalty_amount'),
                avg_confidence=Avg('avg_confidence_score'),
                unique_tracks=Count('track_id', distinct=True)
            )
        
        def get_artist_analytics(artist_id, date_range):
            return PlayLog.objects.filter(
                track__artist_id=artist_id,
                played_at__range=date_range
            ).select_related('track', 'station').aggregate(
                total_plays=Count('id'),
                total_earnings=Sum('royalty_amount'),
                unique_stations=Count('station_id', distinct=True)
            )
        
        return get_station_analytics, get_artist_analytics
    
    @staticmethod
    def optimize_detection_queries():
        """Optimize audio detection queries for processing pipeline"""
        from music_monitor.models import AudioDetection
        
        def get_pending_detections(limit=100):
            return AudioDetection.objects.filter(
                processing_status='pending'
            ).select_related('station').order_by('detected_at')[:limit]
        
        def get_failed_detections_for_retry():
            return AudioDetection.objects.filter(
                processing_status='failed',
                retry_count__lt=3
            ).select_related('station').order_by('detected_at')
        
        return get_pending_detections, get_failed_detections_for_retry


# Database maintenance utilities
class DatabaseMaintenance:
    """Database maintenance and cleanup utilities"""
    
    @staticmethod
    def vacuum_analyze_tables():
        """Run VACUUM ANALYZE on key tables for performance"""
        tables_to_vacuum = [
            'music_monitor_playlog',
            'music_monitor_audiodetection',
            'music_monitor_royaltydistribution',
            'artists_track',
            'artists_fingerprint',
            'accounts_user',
            'stations_station',
        ]
        
        with connection.cursor() as cursor:
            for table in tables_to_vacuum:
                cursor.execute(f"VACUUM ANALYZE {table}")
                logger.info(f"Vacuumed and analyzed table: {table}")
    
    @staticmethod
    def cleanup_old_data(days=90):
        """Clean up old data to maintain performance"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clean up old audit logs
        from accounts.models import AuditLog
        old_logs = AuditLog.objects.filter(timestamp__lt=cutoff_date)
        count = old_logs.count()
        old_logs.delete()
        logger.info(f"Cleaned up {count} old audit log entries")
        
        # Archive old play logs (move to separate table instead of deleting)
        from music_monitor.models import PlayLog
        old_playlogs = PlayLog.objects.filter(
            played_at__lt=cutoff_date,
            claimed=True
        )
        logger.info(f"Found {old_playlogs.count()} old play logs for archival")
    
    @staticmethod
    def update_table_statistics():
        """Update table statistics for query planner"""
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")
            logger.info("Updated database table statistics")


# Performance monitoring
class PerformanceMonitor:
    """Monitor database performance and identify bottlenecks"""
    
    @staticmethod
    def get_slow_queries():
        """Get slow queries from PostgreSQL logs"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT query, calls, total_time, mean_time, rows
                FROM pg_stat_statements 
                WHERE mean_time > 1000
                ORDER BY mean_time DESC
                LIMIT 10
            """)
            
            return cursor.fetchall()
    
    @staticmethod
    def get_table_sizes():
        """Get table sizes for capacity planning"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)
            
            return cursor.fetchall()
    
    @staticmethod
    def monitor_connection_usage():
        """Monitor database connection usage"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    state,
                    count(*) as connections
                FROM pg_stat_activity 
                WHERE datname = current_database()
                GROUP BY state
            """)
            
            return cursor.fetchall()