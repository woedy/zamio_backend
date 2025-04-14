from django.contrib import admin

from fingerprint_engine.models import Fingerprint, Song

# Register your models here.
admin.site.register(Song)
admin.site.register(Fingerprint)