from django.apps import AppConfig


class MusicMonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'music_monitor'


    def ready(self):
        import api.signals