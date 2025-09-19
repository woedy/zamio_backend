"""
Enhanced background processing system for ZamIO platform.
Provides optimized Celery task management, monitoring, and retry mechanisms.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from functools import wraps
from celery import Task, current_task
from celery.exceptions import Retry, WorkerLostError
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import json

logger = logging.getLogger(__name__)


class TaskMonitor:
    """Monitor and track Celery task performance and status"""
    
    CACHE_PREFIX = "task_monitor"
    
    @classmethod
    def _make_key(cls, task_id: str, suffix: str = "") -> str:
        """Create cache key for task monitoring"""
        return f"{cls.CACHE_PREFIX}:{task_id}:{suffix}" if suffix else f"{cls.CACHE_PREFIX}:{task_id}"
    
    @classmethod
    def start_task(cls, task_id: str, task_name: str, args: tuple = None, kwargs: dict = None):
        """Record task start"""
        task_info = {
            'task_id': task_id,
            'task_name': task_name,
            'status': 'STARTED',
            'started_at': timezone.now().isoformat(),
            'args': str(args) if args else None,
            'kwargs': str(kwargs) if kwargs else None,
            'retry_count': 0,
            'progress': 0,
        }
        
        cache.set(cls._make_key(task_id), json.dumps(task_info), timeout=3600)  # 1 hour
        logger.info(f"Task {task_name} ({task_id}) started")
    
    @classmethod
    def update_progress(cls, task_id: str, progress: int, message: str = None):
        """Update task progress"""
        key = cls._make_key(task_id)
        task_info_json = cache.get(key)
        
        if task_info_json:
            task_info = json.loads(task_info_json)
            task_info['progress'] = progress
            task_info['last_update'] = timezone.now().isoformat()
            
            if message:
                task_info['message'] = message
            
            cache.set(key, json.dumps(task_info), timeout=3600)
            logger.debug(f"Task {task_id} progress: {progress}%")
    
    @classmethod
    def complete_task(cls, task_id: str, result: Any = None, error: str = None):
        """Record task completion"""
        key = cls._make_key(task_id)
        task_info_json = cache.get(key)
        
        if task_info_json:
            task_info = json.loads(task_info_json)
            task_info['status'] = 'SUCCESS' if error is None else 'FAILURE'
            task_info['completed_at'] = timezone.now().isoformat()
            task_info['progress'] = 100 if error is None else task_info.get('progress', 0)
            
            if result is not None:
                task_info['result'] = str(result)
            
            if error:
                task_info['error'] = error
            
            # Calculate duration
            started_at = datetime.fromisoformat(task_info['started_at'])
            completed_at = datetime.fromisoformat(task_info['completed_at'])
            task_info['duration_seconds'] = (completed_at - started_at).total_seconds()
            
            cache.set(key, json.dumps(task_info), timeout=86400)  # Keep for 24 hours
            
            status = "completed successfully" if error is None else f"failed: {error}"
            logger.info(f"Task {task_id} {status} in {task_info['duration_seconds']:.2f}s")
    
    @classmethod
    def increment_retry(cls, task_id: str):
        """Increment retry count for task"""
        key = cls._make_key(task_id)
        task_info_json = cache.get(key)
        
        if task_info_json:
            task_info = json.loads(task_info_json)
            task_info['retry_count'] = task_info.get('retry_count', 0) + 1
            task_info['last_retry'] = timezone.now().isoformat()
            
            cache.set(key, json.dumps(task_info), timeout=3600)
            logger.warning(f"Task {task_id} retry #{task_info['retry_count']}")
    
    @classmethod
    def get_task_info(cls, task_id: str) -> Optional[Dict]:
        """Get task information"""
        key = cls._make_key(task_id)
        task_info_json = cache.get(key)
        
        if task_info_json:
            return json.loads(task_info_json)
        
        return None
    
    @classmethod
    def get_active_tasks(cls) -> List[Dict]:
        """Get all active tasks"""
        # This would require scanning cache keys, which is expensive
        # In production, consider using a separate tracking mechanism
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            
            keys = redis_conn.keys(f"{cls.CACHE_PREFIX}:*")
            active_tasks = []
            
            for key in keys:
                task_info_json = redis_conn.get(key)
                if task_info_json:
                    task_info = json.loads(task_info_json.decode('utf-8'))
                    if task_info.get('status') == 'STARTED':
                        active_tasks.append(task_info)
            
            return active_tasks
        except Exception as e:
            logger.error(f"Failed to get active tasks: {e}")
            return []


class EnhancedTask(Task):
    """Enhanced Celery task with monitoring, retry logic, and error handling"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    
    def __call__(self, *args, **kwargs):
        """Override call to add monitoring"""
        task_id = self.request.id
        task_name = self.name
        
        # Start monitoring
        TaskMonitor.start_task(task_id, task_name, args, kwargs)
        
        try:
            result = super().__call__(*args, **kwargs)
            TaskMonitor.complete_task(task_id, result)
            return result
        except Exception as e:
            TaskMonitor.complete_task(task_id, error=str(e))
            raise
    
    def retry(self, args=None, kwargs=None, exc=None, throw=True, eta=None, countdown=None, max_retries=None, **options):
        """Override retry to add monitoring"""
        task_id = self.request.id
        TaskMonitor.increment_retry(task_id)
        
        return super().retry(args, kwargs, exc, throw, eta, countdown, max_retries, **options)


def monitored_task(*task_args, **task_kwargs):
    """Decorator for creating monitored Celery tasks"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Set the task base class
        task_kwargs['base'] = EnhancedTask
        
        return wrapper
    
    return decorator


class BatchProcessor:
    """Utility for processing large datasets in batches"""
    
    def __init__(self, batch_size: int = 100, max_workers: int = 4):
        self.batch_size = batch_size
        self.max_workers = max_workers
    
    def process_in_batches(self, items: List[Any], processor_func: Callable, 
                          task_id: str = None, **processor_kwargs) -> Dict[str, Any]:
        """Process items in batches with progress tracking"""
        total_items = len(items)
        processed = 0
        successful = 0
        failed = 0
        errors = []
        
        # Split items into batches
        batches = [items[i:i + self.batch_size] for i in range(0, total_items, self.batch_size)]
        
        logger.info(f"Processing {total_items} items in {len(batches)} batches")
        
        for batch_idx, batch in enumerate(batches):
            try:
                # Process batch
                batch_result = processor_func(batch, **processor_kwargs)
                
                # Update counters
                batch_successful = batch_result.get('successful', len(batch))
                batch_failed = batch_result.get('failed', 0)
                
                successful += batch_successful
                failed += batch_failed
                processed += len(batch)
                
                # Collect errors
                if 'errors' in batch_result:
                    errors.extend(batch_result['errors'])
                
                # Update progress
                if task_id:
                    progress = int((processed / total_items) * 100)
                    TaskMonitor.update_progress(
                        task_id, 
                        progress, 
                        f"Processed {processed}/{total_items} items"
                    )
                
                logger.info(f"Batch {batch_idx + 1}/{len(batches)} completed: {batch_successful} successful, {batch_failed} failed")
                
            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                failed += len(batch)
                processed += len(batch)
                errors.append(f"Batch {batch_idx + 1}: {str(e)}")
        
        return {
            'total_items': total_items,
            'processed': processed,
            'successful': successful,
            'failed': failed,
            'errors': errors,
            'success_rate': (successful / total_items) * 100 if total_items > 0 else 0
        }


class TaskQueue:
    """Manage task queues and priorities"""
    
    # Queue priorities
    QUEUES = {
        'critical': 'critical',      # Real-time audio processing
        'high': 'high',             # User-facing operations
        'normal': 'normal',         # Regular background tasks
        'low': 'low',              # Batch processing, cleanup
        'analytics': 'analytics',   # Analytics and reporting
    }
    
    @classmethod
    def get_queue_for_task(cls, task_type: str) -> str:
        """Get appropriate queue for task type"""
        queue_mapping = {
            'audio_detection': cls.QUEUES['critical'],
            'fingerprinting': cls.QUEUES['high'],
            'royalty_calculation': cls.QUEUES['normal'],
            'batch_processing': cls.QUEUES['low'],
            'analytics': cls.QUEUES['analytics'],
            'cleanup': cls.QUEUES['low'],
            'sync': cls.QUEUES['normal'],
        }
        
        return queue_mapping.get(task_type, cls.QUEUES['normal'])
    
    @classmethod
    def get_queue_stats(cls) -> Dict[str, Any]:
        """Get statistics for all queues"""
        try:
            from celery import current_app
            
            inspect = current_app.control.inspect()
            active_tasks = inspect.active()
            reserved_tasks = inspect.reserved()
            
            stats = {}
            for queue_name in cls.QUEUES.values():
                stats[queue_name] = {
                    'active': 0,
                    'reserved': 0,
                }
                
                # Count active tasks
                if active_tasks:
                    for worker, tasks in active_tasks.items():
                        for task in tasks:
                            if task.get('delivery_info', {}).get('routing_key') == queue_name:
                                stats[queue_name]['active'] += 1
                
                # Count reserved tasks
                if reserved_tasks:
                    for worker, tasks in reserved_tasks.items():
                        for task in tasks:
                            if task.get('delivery_info', {}).get('routing_key') == queue_name:
                                stats[queue_name]['reserved'] += 1
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}


class PerformanceOptimizer:
    """Optimize task performance based on system resources and load"""
    
    @staticmethod
    def get_optimal_batch_size(task_type: str, system_load: float = None) -> int:
        """Calculate optimal batch size based on task type and system load"""
        base_sizes = {
            'fingerprinting': 10,
            'audio_detection': 5,
            'royalty_calculation': 50,
            'analytics': 100,
            'cleanup': 200,
        }
        
        base_size = base_sizes.get(task_type, 50)
        
        # Adjust based on system load
        if system_load is not None:
            if system_load > 0.8:  # High load
                return max(1, base_size // 2)
            elif system_load < 0.3:  # Low load
                return base_size * 2
        
        return base_size
    
    @staticmethod
    def get_optimal_worker_count(task_type: str) -> int:
        """Get optimal worker count for task type"""
        worker_counts = {
            'fingerprinting': 2,  # CPU intensive
            'audio_detection': 3,  # Real-time processing
            'royalty_calculation': 4,  # Database intensive
            'analytics': 2,  # Memory intensive
            'cleanup': 1,  # Low priority
        }
        
        return worker_counts.get(task_type, 2)
    
    @staticmethod
    def should_throttle_task(task_type: str) -> bool:
        """Determine if task should be throttled based on system resources"""
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            # Throttling thresholds
            thresholds = {
                'fingerprinting': {'cpu': 80, 'memory': 85},
                'audio_detection': {'cpu': 90, 'memory': 90},
                'batch_processing': {'cpu': 70, 'memory': 80},
                'analytics': {'cpu': 75, 'memory': 85},
            }
            
            task_thresholds = thresholds.get(task_type, {'cpu': 80, 'memory': 85})
            
            return (cpu_percent > task_thresholds['cpu'] or 
                   memory_percent > task_thresholds['memory'])
        
        except ImportError:
            # psutil not available, don't throttle
            return False
        except Exception as e:
            logger.warning(f"Failed to check system resources: {e}")
            return False


class TaskScheduler:
    """Smart task scheduling based on priorities and system load"""
    
    @staticmethod
    def schedule_task(task_func: Callable, task_type: str, args: tuple = None, 
                     kwargs: dict = None, priority: str = 'normal', 
                     delay_seconds: int = 0) -> str:
        """Schedule a task with optimal settings"""
        
        # Get optimal queue
        queue = TaskQueue.get_queue_for_task(task_type)
        
        # Check if we should throttle
        if PerformanceOptimizer.should_throttle_task(task_type):
            delay_seconds = max(delay_seconds, 30)  # Add minimum delay
            logger.info(f"Throttling {task_type} task due to high system load")
        
        # Schedule the task
        if delay_seconds > 0:
            eta = timezone.now() + timedelta(seconds=delay_seconds)
            result = task_func.apply_async(
                args=args or (),
                kwargs=kwargs or {},
                queue=queue,
                eta=eta
            )
        else:
            result = task_func.apply_async(
                args=args or (),
                kwargs=kwargs or {},
                queue=queue
            )
        
        logger.info(f"Scheduled {task_type} task {result.id} on queue {queue}")
        return result.id
    
    @staticmethod
    def schedule_batch_task(task_func: Callable, items: List[Any], task_type: str,
                          processor_kwargs: dict = None) -> List[str]:
        """Schedule batch processing tasks"""
        
        # Get optimal batch size
        batch_size = PerformanceOptimizer.get_optimal_batch_size(task_type)
        
        # Split into batches
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        
        task_ids = []
        for batch_idx, batch in enumerate(batches):
            # Add delay between batches to prevent overwhelming
            delay = batch_idx * 5  # 5 seconds between batches
            
            task_id = TaskScheduler.schedule_task(
                task_func,
                task_type,
                args=(batch,),
                kwargs=processor_kwargs or {},
                delay_seconds=delay
            )
            task_ids.append(task_id)
        
        logger.info(f"Scheduled {len(batches)} batch tasks for {len(items)} items")
        return task_ids


class TaskHealthChecker:
    """Monitor task health and detect issues"""
    
    @staticmethod
    def check_stuck_tasks(max_age_hours: int = 2) -> List[Dict]:
        """Find tasks that have been running too long"""
        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
        
        active_tasks = TaskMonitor.get_active_tasks()
        stuck_tasks = []
        
        for task_info in active_tasks:
            started_at = datetime.fromisoformat(task_info['started_at'])
            if started_at < cutoff_time:
                stuck_tasks.append(task_info)
        
        if stuck_tasks:
            logger.warning(f"Found {len(stuck_tasks)} stuck tasks")
        
        return stuck_tasks
    
    @staticmethod
    def check_failed_tasks(hours_back: int = 24) -> List[Dict]:
        """Find recently failed tasks"""
        # This would require a more persistent storage mechanism
        # For now, we'll return empty list
        return []
    
    @staticmethod
    def get_task_performance_metrics() -> Dict[str, Any]:
        """Get task performance metrics"""
        try:
            from celery import current_app
            
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                return {}
            
            # Aggregate metrics from all workers
            total_tasks = 0
            total_errors = 0
            
            for worker, worker_stats in stats.items():
                total_tasks += worker_stats.get('total', {}).get('tasks.total', 0)
                
                # Count errors from different sources
                for key, value in worker_stats.get('total', {}).items():
                    if 'error' in key.lower() or 'fail' in key.lower():
                        total_errors += value
            
            error_rate = (total_errors / total_tasks * 100) if total_tasks > 0 else 0
            
            return {
                'total_tasks': total_tasks,
                'total_errors': total_errors,
                'error_rate': error_rate,
                'worker_count': len(stats),
                'queue_stats': TaskQueue.get_queue_stats()
            }
        
        except Exception as e:
            logger.error(f"Failed to get task metrics: {e}")
            return {}


# Utility functions for common task patterns
def with_progress_tracking(func):
    """Decorator to add progress tracking to tasks"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        task_id = current_task.request.id if current_task else None
        
        if task_id:
            TaskMonitor.update_progress(task_id, 0, "Starting task")
        
        try:
            result = func(*args, **kwargs)
            
            if task_id:
                TaskMonitor.update_progress(task_id, 100, "Task completed")
            
            return result
        except Exception as e:
            if task_id:
                TaskMonitor.complete_task(task_id, error=str(e))
            raise
    
    return wrapper


def with_retry_logic(max_retries: int = 3, countdown: int = 60):
    """Decorator to add retry logic to tasks"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if current_task:
                    raise current_task.retry(
                        exc=exc,
                        countdown=countdown,
                        max_retries=max_retries
                    )
                else:
                    raise
        
        return wrapper
    
    return decorator