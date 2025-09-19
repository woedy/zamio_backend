from django.apps import AppConfig


class DisputesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'disputes'
    verbose_name = 'Dispute Resolution System'
    
    def ready(self):
        # Import signals when the app is ready
        try:
            import disputes.signals
        except ImportError:
            pass