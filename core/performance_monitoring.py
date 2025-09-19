"""
Performance monitoring service for ZamIO platform.
Tracks system performance, task execution metrics, and provides alerting.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import json

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Collect and track performance metrics"""
    
    CACHE_PREFIX = "perf_metrics"
    
    @classmethod
    def _make_key(cls, metric_type: str, identifier: str = "") -> str:
        """Create cache key for metrics"""
        return f"{cls.CACHE_PREFIX}:{metric_type}:{identifier}" if identifier else f"{cls.CACHE_PREFIX}:{metric_type}"
    
    @classmethod
    def record_task_execution(cls, task_name: str, execution_time: float, 
                            success: bool, queue: str = None):
        """Record task execution metrics"""
        timestamp = timezone.now()
        
        # Store individual execution record
        execution_record = {
            'task_name': task_name,
            'execution_time': execution_time,
            'success': success,
            'queue': queue,
            'timestamp': timestamp.isoformat()
        }
        
        # Add to recent executions list
        recent_key = cls._make_key('recent_executions')
        recent_executions = cache.get(recent_key, [])
        recent_executions.append(execution_record)
        
        # Keep only last 100 executions
        if len(recent_executions) > 100:
            recent_executions = recent_executions[-100:]
        
        cache.set(recent_key, recent_executions, timeout=3600)  # 1 hour
        
        # Update aggregated metrics
        cls._update_aggregated_metrics(task_name, execution_time, success)
    
    @classmethod
    def _update_aggregated_metrics(cls, task_name: str, execution_time: float, success: bool):
        """Update aggregated metrics for a task"""
        metrics_key = cls._make_key('aggregated', task_name)
        current_metrics = cache.get(metrics_key, {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_execution_time': 0.0,
            'min_execution_time': float('inf'),
            'max_execution_time': 0.0,
            'last_updated': timezone.now().isoformat()
        })
        
        # Update counters
        current_metrics['total_executions'] += 1
        if success:
            current_metrics['successful_executions'] += 1
        else:
            current_metrics['failed_executions'] += 1
        
        # Update timing metrics
        current_metrics['total_execution_time'] += execution_time
        current_metrics['min_execution_time'] = min(current_metrics['min_execution_time'], execution_time)
        current_metrics['max_execution_time'] = max(current_metrics['max_execution_time'], execution_time)
        current_metrics['last_updated'] = timezone.now().isoformat()
        
        # Calculate derived metrics
        current_metrics['average_execution_time'] = (
            current_metrics['total_execution_time'] / current_metrics['total_executions']
        )
        current_metrics['success_rate'] = (
            current_metrics['successful_executions'] / current_metrics['total_executions'] * 100
        )
        
        cache.set(metrics_key, current_metrics, timeout=86400)  # 24 hours
    
    @classmethod
    def get_task_metrics(cls, task_name: str) -> Optional[Dict]:
        """Get aggregated metrics for a specific task"""
        metrics_key = cls._make_key('aggregated', task_name)
        return cache.get(metrics_key)
    
    @classmethod
    def get_all_task_metrics(cls) -> Dict[str, Dict]:
        """Get metrics for all tasks"""
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            
            pattern = cls._make_key('aggregated', '*')
            keys = redis_conn.keys(pattern)
            
            all_metrics = {}
            for key in keys:
                key_str = key.decode('utf-8')
                task_name = key_str.split(':')[-1]  # Extract task name from key
                
                metrics_json = redis_conn.get(key)
                if metrics_json:
                    all_metrics[task_name] = json.loads(metrics_json.decode('utf-8'))
            
            return all_metrics
        except Exception as e:
            logger.error(f"Failed to get all task metrics: {e}")
            return {}
    
    @classmethod
    def get_recent_executions(cls, limit: int = 50) -> List[Dict]:
        """Get recent task executions"""
        recent_key = cls._make_key('recent_executions')
        recent_executions = cache.get(recent_key, [])
        return recent_executions[-limit:]
    
    @classmethod
    def record_system_metrics(cls):
        """Record system-level performance metrics"""
        try:
            import psutil
            
            system_metrics = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage_percent': psutil.disk_usage('/').percent,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
                'timestamp': timezone.now().isoformat()
            }
            
            # Store system metrics
            system_key = cls._make_key('system_metrics')
            recent_system_metrics = cache.get(system_key, [])
            recent_system_metrics.append(system_metrics)
            
            # Keep only last 24 hours of data (assuming 1 minute intervals)
            if len(recent_system_metrics) > 1440:
                recent_system_metrics = recent_system_metrics[-1440:]
            
            cache.set(system_key, recent_system_metrics, timeout=86400)
            
        except ImportError:
            logger.warning("psutil not available, cannot record system metrics")
        except Exception as e:
            logger.error(f"Failed to record system metrics: {e}")
    
    @classmethod
    def get_system_metrics(cls, hours_back: int = 1) -> List[Dict]:
        """Get system metrics for the specified time period"""
        system_key = cls._make_key('system_metrics')
        all_metrics = cache.get(system_key, [])
        
        # Filter by time period
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        filtered_metrics = []
        for metric in all_metrics:
            metric_time = datetime.fromisoformat(metric['timestamp'])
            if metric_time >= cutoff_time:
                filtered_metrics.append(metric)
        
        return filtered_metrics


class AlertingService:
    """Service for monitoring performance and sending alerts"""
    
    # Alert thresholds
    THRESHOLDS = {
        'task_failure_rate': 20.0,  # Alert if failure rate > 20%
        'task_execution_time': 300.0,  # Alert if avg execution time > 5 minutes
        'system_cpu': 90.0,  # Alert if CPU > 90%
        'system_memory': 95.0,  # Alert if memory > 95%
        'system_disk': 90.0,  # Alert if disk > 90%
        'queue_backlog': 100,  # Alert if queue has > 100 tasks
    }
    
    @classmethod
    def check_task_performance_alerts(cls) -> List[Dict]:
        """Check for task performance issues and generate alerts"""
        alerts = []
        
        # Get all task metrics
        all_metrics = PerformanceMetrics.get_all_task_metrics()
        
        for task_name, metrics in all_metrics.items():
            # Check failure rate
            failure_rate = 100 - metrics.get('success_rate', 100)
            if failure_rate > cls.THRESHOLDS['task_failure_rate']:
                alerts.append({
                    'type': 'task_failure_rate',
                    'severity': 'high',
                    'task_name': task_name,
                    'current_value': failure_rate,
                    'threshold': cls.THRESHOLDS['task_failure_rate'],
                    'message': f'Task {task_name} has high failure rate: {failure_rate:.1f}%'
                })
            
            # Check execution time
            avg_time = metrics.get('average_execution_time', 0)
            if avg_time > cls.THRESHOLDS['task_execution_time']:
                alerts.append({
                    'type': 'task_execution_time',
                    'severity': 'medium',
                    'task_name': task_name,
                    'current_value': avg_time,
                    'threshold': cls.THRESHOLDS['task_execution_time'],
                    'message': f'Task {task_name} has slow execution time: {avg_time:.1f}s'
                })
        
        return alerts
    
    @classmethod
    def check_system_alerts(cls) -> List[Dict]:
        """Check for system-level performance issues"""
        alerts = []
        
        # Get recent system metrics
        recent_metrics = PerformanceMetrics.get_system_metrics(hours_back=1)
        
        if not recent_metrics:
            return alerts
        
        # Get latest metrics
        latest_metrics = recent_metrics[-1]
        
        # Check CPU usage
        cpu_percent = latest_metrics.get('cpu_percent', 0)
        if cpu_percent > cls.THRESHOLDS['system_cpu']:
            alerts.append({
                'type': 'system_cpu',
                'severity': 'high',
                'current_value': cpu_percent,
                'threshold': cls.THRESHOLDS['system_cpu'],
                'message': f'High CPU usage: {cpu_percent:.1f}%'
            })
        
        # Check memory usage
        memory_percent = latest_metrics.get('memory_percent', 0)
        if memory_percent > cls.THRESHOLDS['system_memory']:
            alerts.append({
                'type': 'system_memory',
                'severity': 'critical',
                'current_value': memory_percent,
                'threshold': cls.THRESHOLDS['system_memory'],
                'message': f'High memory usage: {memory_percent:.1f}%'
            })
        
        # Check disk usage
        disk_percent = latest_metrics.get('disk_usage_percent', 0)
        if disk_percent > cls.THRESHOLDS['system_disk']:
            alerts.append({
                'type': 'system_disk',
                'severity': 'high',
                'current_value': disk_percent,
                'threshold': cls.THRESHOLDS['system_disk'],
                'message': f'High disk usage: {disk_percent:.1f}%'
            })
        
        return alerts
    
    @classmethod
    def check_queue_alerts(cls) -> List[Dict]:
        """Check for queue backlog issues"""
        alerts = []
        
        try:
            from core.background_processing import TaskQueue
            queue_stats = TaskQueue.get_queue_stats()
            
            for queue_name, stats in queue_stats.items():
                total_tasks = stats.get('active', 0) + stats.get('reserved', 0)
                
                if total_tasks > cls.THRESHOLDS['queue_backlog']:
                    alerts.append({
                        'type': 'queue_backlog',
                        'severity': 'medium',
                        'queue_name': queue_name,
                        'current_value': total_tasks,
                        'threshold': cls.THRESHOLDS['queue_backlog'],
                        'message': f'Queue {queue_name} has backlog: {total_tasks} tasks'
                    })
        
        except Exception as e:
            logger.error(f"Failed to check queue alerts: {e}")
        
        return alerts
    
    @classmethod
    def get_all_alerts(cls) -> Dict[str, List[Dict]]:
        """Get all current alerts"""
        return {
            'task_performance': cls.check_task_performance_alerts(),
            'system_performance': cls.check_system_alerts(),
            'queue_performance': cls.check_queue_alerts()
        }
    
    @classmethod
    def send_alert_notification(cls, alert: Dict):
        """Send alert notification (placeholder for actual implementation)"""
        # This would integrate with notification services like:
        # - Email notifications
        # - Slack/Discord webhooks
        # - SMS alerts
        # - Dashboard notifications
        
        logger.warning(f"ALERT: {alert['message']} (Severity: {alert['severity']})")
        
        # Store alert in cache for dashboard display
        alerts_key = "performance_alerts"
        current_alerts = cache.get(alerts_key, [])
        
        alert['timestamp'] = timezone.now().isoformat()
        current_alerts.append(alert)
        
        # Keep only last 50 alerts
        if len(current_alerts) > 50:
            current_alerts = current_alerts[-50:]
        
        cache.set(alerts_key, current_alerts, timeout=86400)


class PerformanceReporter:
    """Generate performance reports and summaries"""
    
    @classmethod
    def generate_daily_report(cls) -> Dict[str, Any]:
        """Generate daily performance report"""
        # Get task metrics
        all_task_metrics = PerformanceMetrics.get_all_task_metrics()
        
        # Get system metrics for last 24 hours
        system_metrics = PerformanceMetrics.get_system_metrics(hours_back=24)
        
        # Calculate summary statistics
        total_executions = sum(metrics.get('total_executions', 0) for metrics in all_task_metrics.values())
        total_failures = sum(metrics.get('failed_executions', 0) for metrics in all_task_metrics.values())
        
        overall_success_rate = ((total_executions - total_failures) / total_executions * 100) if total_executions > 0 else 100
        
        # Find slowest and fastest tasks
        slowest_task = None
        fastest_task = None
        
        for task_name, metrics in all_task_metrics.items():
            avg_time = metrics.get('average_execution_time', 0)
            
            if slowest_task is None or avg_time > slowest_task['avg_time']:
                slowest_task = {'name': task_name, 'avg_time': avg_time}
            
            if fastest_task is None or avg_time < fastest_task['avg_time']:
                fastest_task = {'name': task_name, 'avg_time': avg_time}
        
        # Calculate system averages
        avg_cpu = sum(m.get('cpu_percent', 0) for m in system_metrics) / len(system_metrics) if system_metrics else 0
        avg_memory = sum(m.get('memory_percent', 0) for m in system_metrics) / len(system_metrics) if system_metrics else 0
        
        # Get current alerts
        current_alerts = AlertingService.get_all_alerts()
        total_alerts = sum(len(alerts) for alerts in current_alerts.values())
        
        report = {
            'report_date': timezone.now().date().isoformat(),
            'task_summary': {
                'total_executions': total_executions,
                'total_failures': total_failures,
                'overall_success_rate': overall_success_rate,
                'unique_tasks': len(all_task_metrics),
                'slowest_task': slowest_task,
                'fastest_task': fastest_task
            },
            'system_summary': {
                'average_cpu_percent': avg_cpu,
                'average_memory_percent': avg_memory,
                'data_points': len(system_metrics)
            },
            'alerts_summary': {
                'total_alerts': total_alerts,
                'by_category': {category: len(alerts) for category, alerts in current_alerts.items()}
            },
            'recommendations': cls._generate_recommendations(all_task_metrics, system_metrics, current_alerts)
        }
        
        return report
    
    @classmethod
    def _generate_recommendations(cls, task_metrics: Dict, system_metrics: List, alerts: Dict) -> List[str]:
        """Generate performance recommendations based on metrics"""
        recommendations = []
        
        # Task-based recommendations
        high_failure_tasks = [
            name for name, metrics in task_metrics.items()
            if metrics.get('success_rate', 100) < 80
        ]
        
        if high_failure_tasks:
            recommendations.append(
                f"Investigate high failure rate tasks: {', '.join(high_failure_tasks[:3])}"
            )
        
        slow_tasks = [
            name for name, metrics in task_metrics.items()
            if metrics.get('average_execution_time', 0) > 120  # > 2 minutes
        ]
        
        if slow_tasks:
            recommendations.append(
                f"Optimize slow-running tasks: {', '.join(slow_tasks[:3])}"
            )
        
        # System-based recommendations
        if system_metrics:
            avg_cpu = sum(m.get('cpu_percent', 0) for m in system_metrics) / len(system_metrics)
            avg_memory = sum(m.get('memory_percent', 0) for m in system_metrics) / len(system_metrics)
            
            if avg_cpu > 70:
                recommendations.append("Consider scaling up CPU resources or optimizing CPU-intensive tasks")
            
            if avg_memory > 80:
                recommendations.append("Monitor memory usage and consider increasing available memory")
        
        # Alert-based recommendations
        total_alerts = sum(len(alert_list) for alert_list in alerts.values())
        if total_alerts > 5:
            recommendations.append("High number of alerts detected - review system configuration and thresholds")
        
        if not recommendations:
            recommendations.append("System performance is within normal parameters")
        
        return recommendations
    
    @classmethod
    def export_metrics_csv(cls, hours_back: int = 24) -> str:
        """Export metrics to CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['timestamp', 'task_name', 'execution_time', 'success', 'queue'])
        
        # Get recent executions
        recent_executions = PerformanceMetrics.get_recent_executions(limit=1000)
        
        # Filter by time period
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        for execution in recent_executions:
            execution_time = datetime.fromisoformat(execution['timestamp'])
            if execution_time >= cutoff_time:
                writer.writerow([
                    execution['timestamp'],
                    execution['task_name'],
                    execution['execution_time'],
                    execution['success'],
                    execution.get('queue', 'unknown')
                ])
        
        return output.getvalue()


# Decorator for automatic performance tracking
def track_performance(func):
    """Decorator to automatically track function performance"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        success = True
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            raise
        finally:
            execution_time = time.time() - start_time
            PerformanceMetrics.record_task_execution(
                func.__name__,
                execution_time,
                success
            )
    
    return wrapper