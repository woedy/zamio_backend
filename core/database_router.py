"""
Database router for read/write splitting to improve performance.
Routes read queries to read replicas and write queries to primary database.
"""

import logging

logger = logging.getLogger(__name__)


class DatabaseRouter:
    """
    A router to control all database operations on models for different
    databases to improve performance through read/write splitting.
    """
    
    # Models that should always use the primary database
    PRIMARY_ONLY_MODELS = {
        'accounts.User',
        'accounts.UserPermission',
        'accounts.AuditLog',
        'artists.Track',
        'artists.Contributor',
        'music_monitor.PlayLog',
        'music_monitor.AudioDetection',
        'music_monitor.RoyaltyDistribution',
        'royalties.RoyaltyCycle',
        'royalties.RoyaltyLineItem',
    }
    
    # Models that can use read replicas for read operations
    READ_REPLICA_MODELS = {
        'artists.Artist',
        'artists.Album',
        'artists.Genre',
        'artists.Fingerprint',
        'stations.Station',
        'stations.StationStaff',
        'publishers.PublisherProfile',
        'royalties.PartnerPRO',
        'royalties.ExternalWork',
        'royalties.ExternalRecording',
    }
    
    def db_for_read(self, model, **hints):
        """Suggest the database to read from."""
        model_name = f"{model._meta.app_label}.{model._meta.object_name}"
        
        # Always use primary for critical models
        if model_name in self.PRIMARY_ONLY_MODELS:
            return 'default'
        
        # Use read replica for analytics and reporting queries
        if model_name in self.READ_REPLICA_MODELS:
            # Check if read replica is available
            from django.conf import settings
            if 'read_replica' in settings.DATABASES:
                logger.debug(f"Routing read query for {model_name} to read replica")
                return 'read_replica'
        
        # Default to primary database
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Suggest the database to write to."""
        # All writes go to primary database
        model_name = f"{model._meta.app_label}.{model._meta.object_name}"
        logger.debug(f"Routing write query for {model_name} to primary database")
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the same app or both use primary DB."""
        db_set = {'default', 'read_replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure that migrations only run on the primary database."""
        if db == 'read_replica':
            return False
        return db == 'default'


class AnalyticsRouter:
    """
    Specialized router for analytics queries to ensure they use read replicas
    when available and don't impact primary database performance.
    """
    
    def db_for_read(self, model, **hints):
        """Route analytics queries to read replica."""
        # Check if this is an analytics query based on hints
        if hints.get('analytics_query', False):
            from django.conf import settings
            if 'read_replica' in settings.DATABASES:
                logger.debug("Routing analytics query to read replica")
                return 'read_replica'
        
        return None  # Let other routers handle
    
    def db_for_write(self, model, **hints):
        """Analytics queries should not write."""
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations for analytics."""
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """No migrations for analytics router."""
        return None


class CacheAwareQuerySet:
    """
    Mixin for QuerySets that are cache-aware and can route queries
    appropriately based on caching strategy.
    """
    
    def using_read_replica(self):
        """Force this queryset to use read replica."""
        from django.conf import settings
        if 'read_replica' in settings.DATABASES:
            return self.using('read_replica')
        return self
    
    def for_analytics(self):
        """Mark this queryset as an analytics query."""
        # This would be used with custom QuerySet implementations
        # to hint to the router that this is an analytics query
        return self.using_read_replica()


# Utility functions for manual database selection
def use_read_replica():
    """Context manager to force queries to use read replica."""
    from django.db import connections
    from django.conf import settings
    
    class ReadReplicaContext:
        def __enter__(self):
            if 'read_replica' in settings.DATABASES:
                return connections['read_replica']
            return connections['default']
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return ReadReplicaContext()


def get_analytics_connection():
    """Get database connection optimized for analytics queries."""
    from django.db import connections
    from django.conf import settings
    
    if 'read_replica' in settings.DATABASES:
        return connections['read_replica']
    return connections['default']


# Performance monitoring for database routing
class DatabaseRoutingMonitor:
    """Monitor database routing decisions for performance analysis."""
    
    @staticmethod
    def log_query_routing(model, operation, database):
        """Log database routing decisions for analysis."""
        logger.info(f"Database routing: {model} {operation} -> {database}")
    
    @staticmethod
    def get_routing_stats():
        """Get statistics on database routing decisions."""
        # This would integrate with Django's database instrumentation
        # to provide insights into query distribution
        pass


# Custom manager for models that should prefer read replicas
class ReadReplicaManager:
    """Manager that prefers read replicas for read operations."""
    
    def get_queryset(self):
        """Return queryset that prefers read replica."""
        queryset = super().get_queryset()
        
        # Use read replica for read operations when available
        from django.conf import settings
        if 'read_replica' in settings.DATABASES:
            return queryset.using('read_replica')
        
        return queryset
    
    def using_primary(self):
        """Force queries to use primary database."""
        return super().get_queryset().using('default')


# Database health monitoring
class DatabaseHealthMonitor:
    """Monitor database health and connection status."""
    
    @staticmethod
    def check_database_health():
        """Check health of all configured databases."""
        from django.db import connections
        from django.conf import settings
        
        health_status = {}
        
        for db_name in settings.DATABASES.keys():
            try:
                connection = connections[db_name]
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                
                health_status[db_name] = {
                    'status': 'healthy',
                    'connection_count': len(connection.queries),
                }
                
            except Exception as e:
                health_status[db_name] = {
                    'status': 'unhealthy',
                    'error': str(e),
                }
                logger.error(f"Database {db_name} health check failed: {e}")
        
        return health_status
    
    @staticmethod
    def get_connection_stats():
        """Get connection statistics for all databases."""
        from django.db import connections
        
        stats = {}
        for db_name, connection in connections.databases.items():
            stats[db_name] = {
                'queries_count': len(connection.queries) if hasattr(connection, 'queries') else 0,
                'vendor': connection.vendor if hasattr(connection, 'vendor') else 'unknown',
            }
        
        return stats