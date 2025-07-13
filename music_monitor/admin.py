from django.contrib import admin

from music_monitor.models import MatchCache, PlayLog, StreamLog

# Register your models here.
admin.site.register(MatchCache)
admin.site.register(PlayLog)
admin.site.register(StreamLog)
