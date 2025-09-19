"""
Django management command to monitor and manage Celery background tasks.
Provides insights into task performance, queue status, and system health.
"""

from django.core.management.base import BaseCommand, CommandError
from core.background_processing import TaskMonitor, TaskQueue, TaskHealthChecker, PerformanceOptimizer
from core.caching_service import CacheMonitor
import logging
import json

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor and manage Celery background tasks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--queue-stats',
            action='store_true',
            help='Show queue statistics and status',
        )
        parser.add_argument(
            '--active-tasks',
            action='store_true',
            help='Show currently active tasks',
        )
        parser.add_argument(
            '--task-performance',
            action='store_true',
            help='Show task performance metrics',
        )
        parser.add_argument(
            '--stuck-tasks',
            action='store_true',
            help='Find tasks that have been running too long',
        )
        parser.add_argument(
            '--system-health',
            action='store_true',
            help='Check overall system health',
        )
        parser.add_argument(
            '--cache-stats',
            action='store_true',
            help='Show cache performance statistics',
        )
        parser.add_argument(
            '--task-id',
            type=str,
            help='Get information about a specific task',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Show all monitoring information',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output in JSON format',
        )
    
    def handle(self, *args, **options):
        self.json_output = options['json']
        
        try:
            if options['all']:
                self._show_all_monitoring_info()
            else:
                if options['queue_stats']:
                    self._show_queue_stats()
                
                if options['active_tasks']:
                    self._show_active_tasks()
                
                if options['task_performance']:
                    self._show_task_performance()
                
                if options['stuck_tasks']:
                    self._show_stuck_tasks()
                
                if options['system_health']:
                    self._show_system_health()
                
                if options['cache_stats']:
                    self._show_cache_stats()
                
                if options['task_id']:
                    self._show_task_info(options['task_id'])
            
            if not any([
                options['all'], options['queue_stats'], options['active_tasks'],
                options['task_performance'], options['stuck_tasks'], 
                options['system_health'], options['cache_stats'], options['task_id']
            ]):
                self._show_summary()
                
        except Exception as e:
            logger.error(f"Task monitoring failed: {e}")
            raise CommandError(f'Task monitoring failed: {e}')
    
    def _output(self, title: str, data: dict):
        """Output data in requested format"""
        if self.json_output:
            output = {title.lower().replace(' ', '_'): data}
            self.stdout.write(json.dumps(output, indent=2, default=str))
        else:
            self.stdout.write(f'\n{title}:')
            self.stdout.write('=' * len(title))
            self._format_dict_output(data)
    
    def _format_dict_output(self, data: dict, indent: int = 0):
        """Format dictionary for human-readable output"""
        for key, value in data.items():
            prefix = '  ' * indent
            if isinstance(value, dict):
                self.stdout.write(f'{prefix}{key}:')
                self._format_dict_output(value, indent + 1)
            elif isinstance(value, list):
                self.stdout.write(f'{prefix}{key}: [{len(value)} items]')
                for i, item in enumerate(value[:5]):  # Show first 5 items
                    if isinstance(item, dict):
                        self.stdout.write(f'{prefix}  [{i}]:')
                        self._format_dict_output(item, indent + 2)
                    else:
                        self.stdout.write(f'{prefix}  [{i}]: {item}')
                if len(value) > 5:
                    self.stdout.write(f'{prefix}  ... and {len(value) - 5} more')
            else:
                self.stdout.write(f'{prefix}{key}: {value}')
    
    def _show_all_monitoring_info(self):
        """Show all monitoring information"""
        self._show_queue_stats()
        self._show_active_tasks()
        self._show_task_performance()
        self._show_stuck_tasks()
        self._show_system_health()
        self._show_cache_stats()
    
    def _show_queue_stats(self):
        """Show queue statistics"""
        try:
            queue_stats = TaskQueue.get_queue_stats()
            
            if queue_stats:
                self._output('Queue Statistics', queue_stats)
            else:
                self.stdout.write('No queue statistics available (Celery may not be running)')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get queue stats: {e}'))
    
    def _show_active_tasks(self):
        """Show currently active tasks"""
        try:
            active_tasks = TaskMonitor.get_active_tasks()
            
            if active_tasks:
                # Summarize active tasks
                task_summary = {}
                for task in active_tasks:
                    task_name = task.get('task_name', 'unknown')
                    if task_name not in task_summary:
                        task_summary[task_name] = 0
                    task_summary[task_name] += 1
                
                summary_data = {
                    'total_active_tasks': len(active_tasks),
                    'tasks_by_type': task_summary,
                    'recent_tasks': active_tasks[:5]  # Show 5 most recent
                }
                
                self._output('Active Tasks', summary_data)
            else:
                self.stdout.write('No active tasks found')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get active tasks: {e}'))
    
    def _show_task_performance(self):
        """Show task performance metrics"""
        try:
            performance_metrics = TaskHealthChecker.get_task_performance_metrics()
            
            if performance_metrics:
                self._output('Task Performance Metrics', performance_metrics)
            else:
                self.stdout.write('No performance metrics available')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get performance metrics: {e}'))
    
    def _show_stuck_tasks(self):
        """Show tasks that may be stuck"""
        try:
            stuck_tasks = TaskHealthChecker.check_stuck_tasks()
            
            if stuck_tasks:
                stuck_data = {
                    'count': len(stuck_tasks),
                    'tasks': stuck_tasks
                }
                self._output('Stuck Tasks (Running > 2 hours)', stuck_data)
                
                # Show recommendations
                if not self.json_output:
                    self.stdout.write('\nRecommendations:')
                    self.stdout.write('  - Check if these tasks are actually processing or stuck')
                    self.stdout.write('  - Consider restarting Celery workers if tasks are truly stuck')
                    self.stdout.write('  - Review task implementation for potential infinite loops')
            else:
                self.stdout.write('No stuck tasks found')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to check stuck tasks: {e}'))
    
    def _show_system_health(self):
        """Show overall system health"""
        try:
            # Check system resources
            should_throttle_fingerprinting = PerformanceOptimizer.should_throttle_task('fingerprinting')
            should_throttle_detection = PerformanceOptimizer.should_throttle_task('audio_detection')
            
            # Get optimal batch sizes
            optimal_fingerprint_batch = PerformanceOptimizer.get_optimal_batch_size('fingerprinting')
            optimal_detection_batch = PerformanceOptimizer.get_optimal_batch_size('audio_detection')
            
            health_data = {
                'throttling_recommended': {
                    'fingerprinting': should_throttle_fingerprinting,
                    'audio_detection': should_throttle_detection,
                },
                'optimal_batch_sizes': {
                    'fingerprinting': optimal_fingerprint_batch,
                    'audio_detection': optimal_detection_batch,
                },
                'worker_recommendations': {
                    'fingerprinting': PerformanceOptimizer.get_optimal_worker_count('fingerprinting'),
                    'audio_detection': PerformanceOptimizer.get_optimal_worker_count('audio_detection'),
                    'royalty_calculation': PerformanceOptimizer.get_optimal_worker_count('royalty_calculation'),
                }
            }
            
            # Try to get system metrics if psutil is available
            try:
                import psutil
                health_data['system_metrics'] = {
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_usage_percent': psutil.disk_usage('/').percent,
                }
            except ImportError:
                health_data['system_metrics'] = 'psutil not available'
            
            self._output('System Health', health_data)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to check system health: {e}'))
    
    def _show_cache_stats(self):
        """Show cache performance statistics"""
        try:
            cache_stats = CacheMonitor.get_cache_stats()
            
            if cache_stats:
                self._output('Cache Statistics', cache_stats)
                
                # Show recommendations based on hit rate
                hit_rate = cache_stats.get('hit_rate', 0)
                if not self.json_output:
                    self.stdout.write('\nCache Performance Analysis:')
                    if hit_rate > 80:
                        self.stdout.write('  ✓ Excellent cache performance')
                    elif hit_rate > 60:
                        self.stdout.write('  ⚠ Good cache performance, consider optimizing cache keys')
                    elif hit_rate > 40:
                        self.stdout.write('  ⚠ Moderate cache performance, review caching strategy')
                    else:
                        self.stdout.write('  ✗ Poor cache performance, investigate cache usage patterns')
            else:
                self.stdout.write('No cache statistics available (Redis may not be running)')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get cache stats: {e}'))
    
    def _show_task_info(self, task_id: str):
        """Show information about a specific task"""
        try:
            task_info = TaskMonitor.get_task_info(task_id)
            
            if task_info:
                self._output(f'Task Information ({task_id})', task_info)
            else:
                self.stdout.write(f'No information found for task {task_id}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get task info: {e}'))
    
    def _show_summary(self):
        """Show a quick summary of system status"""
        try:
            # Get basic stats
            active_tasks = TaskMonitor.get_active_tasks()
            stuck_tasks = TaskHealthChecker.check_stuck_tasks()
            cache_stats = CacheMonitor.get_cache_stats()
            
            summary = {
                'active_tasks': len(active_tasks),
                'stuck_tasks': len(stuck_tasks),
                'cache_hit_rate': cache_stats.get('hit_rate', 0) if cache_stats else 0,
                'status': 'healthy' if len(stuck_tasks) == 0 else 'warning'
            }
            
            if self.json_output:
                self.stdout.write(json.dumps(summary, indent=2))
            else:
                self.stdout.write('ZamIO Background Processing Summary:')
                self.stdout.write('=' * 40)
                self.stdout.write(f'Active Tasks: {summary["active_tasks"]}')
                self.stdout.write(f'Stuck Tasks: {summary["stuck_tasks"]}')
                self.stdout.write(f'Cache Hit Rate: {summary["cache_hit_rate"]:.1f}%')
                
                status_color = self.style.SUCCESS if summary['status'] == 'healthy' else self.style.WARNING
                self.stdout.write(f'Overall Status: {status_color(summary["status"].upper())}')
                
                self.stdout.write('\nFor detailed information, use:')
                self.stdout.write('  python manage.py monitor_tasks --all')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to generate summary: {e}'))