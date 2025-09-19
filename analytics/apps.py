from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    
    def ready(self):
        # Import signals to ensure they're registered
        try:
            from . import signals
        except ImportError:
            pass