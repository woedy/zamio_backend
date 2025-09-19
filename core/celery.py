import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Enhanced Celery configuration for performance optimization
app.conf.update(
    # Task routing and queues
    task_routes={
        'core.enhanced_tasks.enhanced_audio_detection_task': {'queue': 'critical'},
        'core.enhanced_tasks.batch_fingerprint_tracks_task': {'queue': 'high'},
        'core.enhanced_tasks.calculate_royalty_distributions_task': {'queue': 'normal'},
        'core.enhanced_tasks.generate_analytics_report_task': {'queue': 'analytics'},
        'core.enhanced_tasks.cleanup_old_data_task': {'queue': 'low'},
        'music_monitor.tasks.*': {'queue': 'normal'},
        'royalties.tasks.*': {'queue': 'normal'},
    },
    
    # Queue definitions with priorities
    task_queues=(
        Queue('critical', routing_key='critical', priority=10),
        Queue('high', routing_key='high', priority=8),
        Queue('normal', routing_key='normal', priority=5),
        Queue('analytics', routing_key='analytics', priority=3),
        Queue('low', routing_key='low', priority=1),
    ),
    
    # Performance optimizations
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Result backend configuration
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Task execution settings
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes
    
    # Monitoring and logging
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
)

# Enhanced beat schedule with performance monitoring
CELERY_BEAT_SCHEDULE = {
    # Existing tasks
    'convert-matches-every-2-minutes': {
        'task': 'music_monitor.tasks.run_matchcache_to_playlog',
        'schedule': crontab(minute='*/2'),
        'options': {'queue': 'normal'}
    },
    'scan-station-streams-every-2-minutes': {
        'task': 'music_monitor.scan_station_streams',
        'schedule': crontab(minute='*/2'),
        'options': {'queue': 'normal'}
    },
    
    # New enhanced tasks
    'auto-fingerprint-new-tracks': {
        'task': 'music_monitor.tasks.auto_fingerprint_new_tracks',
        'schedule': crontab(minute='*/10'),  # every 10 minutes
        'options': {'queue': 'high'}
    },
    'cleanup-old-fingerprints': {
        'task': 'music_monitor.tasks.cleanup_old_fingerprints',
        'schedule': crontab(hour=2, minute=0),  # daily at 2 AM
        'options': {'queue': 'low'}
    },
    'warm-cache-hourly': {
        'task': 'core.enhanced_tasks.warm_cache_task',
        'schedule': crontab(minute=0),  # every hour
        'options': {'queue': 'low'}
    },
    'cleanup-old-data-daily': {
        'task': 'core.enhanced_tasks.cleanup_old_data_task',
        'schedule': crontab(hour=3, minute=0),  # daily at 3 AM
        'options': {'queue': 'low'}
    },
    'update-pro-mappings': {
        'task': 'music_monitor.tasks.batch_update_pro_mappings',
        'schedule': crontab(hour=1, minute=0),  # daily at 1 AM
        'options': {'queue': 'normal'}
    },
}

app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
