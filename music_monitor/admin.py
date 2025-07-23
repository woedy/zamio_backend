from django.contrib import admin

from music_monitor.models import Dispute, FailedPlayLog, MatchCache, PlayLog, StreamLog

# Register your models here.
admin.site.register(MatchCache)
admin.site.register(PlayLog)
admin.site.register(FailedPlayLog)
admin.site.register(StreamLog)
admin.site.register(Dispute)
