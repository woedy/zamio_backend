import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


CELERY_BEAT_SCHEDULE = {
    'convert-matches-every-2-minutes': {
        'task': 'music_monitor.tasks.run_matchcache_to_playlog',
        'schedule': crontab(minute='*/2'),  # every 2 minutes
    },
}