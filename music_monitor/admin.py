# api/admin.py
from django.contrib import admin
from .models import Artist, Track, Station, PlayLog

admin.site.register(Artist)
admin.site.register(Track)
admin.site.register(Station)
admin.site.register(PlayLog)
