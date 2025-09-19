"""
Django management command to optimize database performance by creating indexes,
analyzing tables, and setting up performance monitoring.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from core.database_optimization import DatabaseOptimizer, QueryOptimizer, DatabaseMaintenance, PerformanceMonitor
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Optimize database performance with indexes and maintenance tasks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Create database indexes for frequently queried fields',
        )
        parser.add_argument(
            '--analyze-tables',
            action='store_true',
            help='Run ANALYZE on all tables to update statistics',
        )
        parser.add_argument(
            '--vacuum-tables',
            action='store_true',
            help='Run VACUUM ANALYZE on key tables',
        )
        parser.add_argument(
            '--cleanup-old-data',
            action='store_true',
            help='Clean up old data (older than 90 days)',
        )
        parser.add_argument(
            '--monitor-performance',
            action='store_true',
            help='Display performance monitoring information',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimization tasks',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting database optimization...')
        )
        
        # Check if we're using PostgreSQL
        if not self._is_postgresql():
            self.stdout.write(
                self.style.WARNING('Some optimizations require PostgreSQL. Current database may not support all features.')
            )
        
        try:
            if options['all']:
                self._run_all_optimizations(options['dry_run'])
            else:
                if options['create_indexes']:
                    self._create_indexes(options['dry_run'])
                
                if options['analyze_tables']:
                    self._analyze_tables(options['dry_run'])
                
                if options['vacuum_tables']:
                    self._vacuum_tables(options['dry_run'])
                
                if options['cleanup_old_data']:
                    self._cleanup_old_data(options['dry_run'])
                
                if options['monitor_performance']:
                    self._monitor_performance()
            
            self.stdout.write(
                self.style.SUCCESS('Database optimization completed successfully!')
            )
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            raise CommandError(f'Database optimization failed: {e}')
    
    def _is_postgresql(self):
        """Check if the database backend is PostgreSQL"""
        return 'postgresql' in connection.settings_dict['ENGINE']
    
    def _run_all_optimizations(self, dry_run=False):
        """Run all optimization tasks"""
        self.stdout.write('Running all optimization tasks...')
        
        self._create_indexes(dry_run)
        self._analyze_tables(dry_run)
        self._vacuum_tables(dry_run)
        self._cleanup_old_data(dry_run)
        self._monitor_performance()
    
    def _create_indexes(self, dry_run=False):
        """Create database indexes for performance"""
        self.stdout.write('Creating database indexes...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: Would create the following indexes:'))
            
            # Show what indexes would be created
            missing_indexes = DatabaseOptimizer.get_missing_indexes()
            for model, fields in missing_indexes:
                self.stdout.write(f'  - Index on {model} for fields: {fields}')
            
            return
        
        try:
            # Create composite indexes
            DatabaseOptimizer.create_composite_indexes()
            self.stdout.write(self.style.SUCCESS('✓ Created composite indexes'))
            
            # Optimize frequent queries
            DatabaseOptimizer.optimize_frequent_queries()
            self.stdout.write(self.style.SUCCESS('✓ Optimized frequent queries'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create indexes: {e}'))
            raise
    
    def _analyze_tables(self, dry_run=False):
        """Analyze tables to update statistics"""
        self.stdout.write('Analyzing tables...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: Would analyze all tables'))
            return
        
        try:
            DatabaseMaintenance.update_table_statistics()
            self.stdout.write(self.style.SUCCESS('✓ Updated table statistics'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to analyze tables: {e}'))
            raise
    
    def _vacuum_tables(self, dry_run=False):
        """Vacuum and analyze key tables"""
        self.stdout.write('Vacuuming tables...')
        
        if not self._is_postgresql():
            self.stdout.write(self.style.WARNING('VACUUM is PostgreSQL-specific, skipping...'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: Would vacuum key tables'))
            return
        
        try:
            DatabaseMaintenance.vacuum_analyze_tables()
            self.stdout.write(self.style.SUCCESS('✓ Vacuumed and analyzed tables'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to vacuum tables: {e}'))
            raise
    
    def _cleanup_old_data(self, dry_run=False):
        """Clean up old data"""
        self.stdout.write('Cleaning up old data...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: Would clean up data older than 90 days'))
            return
        
        try:
            DatabaseMaintenance.cleanup_old_data()
            self.stdout.write(self.style.SUCCESS('✓ Cleaned up old data'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to clean up old data: {e}'))
            raise
    
    def _monitor_performance(self):
        """Display performance monitoring information"""
        self.stdout.write('Performance Monitoring Information:')
        self.stdout.write('=' * 50)
        
        try:
            # Get table sizes
            table_sizes = PerformanceMonitor.get_table_sizes()
            if table_sizes:
                self.stdout.write('\nTable Sizes:')
                for schema, table, size, size_bytes in table_sizes[:10]:
                    self.stdout.write(f'  {table}: {size}')
            
            # Get connection usage
            connections = PerformanceMonitor.monitor_connection_usage()
            if connections:
                self.stdout.write('\nDatabase Connections:')
                for state, count in connections:
                    self.stdout.write(f'  {state}: {count}')
            
            # Get slow queries (if pg_stat_statements is available)
            if self._is_postgresql():
                try:
                    slow_queries = PerformanceMonitor.get_slow_queries()
                    if slow_queries:
                        self.stdout.write('\nSlow Queries (>1 second):')
                        for query, calls, total_time, mean_time, rows in slow_queries[:5]:
                            self.stdout.write(f'  Mean time: {mean_time:.2f}ms, Calls: {calls}')
                            self.stdout.write(f'    Query: {query[:100]}...')
                except Exception:
                    self.stdout.write('\nSlow query monitoring requires pg_stat_statements extension')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get performance information: {e}'))
    
    def _show_optimization_recommendations(self):
        """Show optimization recommendations"""
        self.stdout.write('\nOptimization Recommendations:')
        self.stdout.write('=' * 40)
        
        recommendations = [
            "1. Run this command weekly: python manage.py optimize_database --all",
            "2. Monitor slow queries and add indexes as needed",
            "3. Set up automated VACUUM and ANALYZE for PostgreSQL",
            "4. Consider partitioning large tables (play_logs, detections)",
            "5. Implement read replicas for analytics queries",
            "6. Use connection pooling (pgbouncer) for production",
            "7. Monitor cache hit rates and adjust cache timeouts",
            "8. Archive old data to separate tables or storage",
        ]
        
        for recommendation in recommendations:
            self.stdout.write(f'  {recommendation}')
        
        self.stdout.write('\nFor more detailed analysis, consider using:')
        self.stdout.write('  - pg_stat_statements for query analysis')
        self.stdout.write('  - pg_stat_user_tables for table statistics')
        self.stdout.write('  - EXPLAIN ANALYZE for specific query optimization')