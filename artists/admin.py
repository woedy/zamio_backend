from django.contrib import admin

from artists.models import Album, Artist, Contributor, Fingerprint, Genre, PlatformAvailability, Track, TrackFeedback

# Register your models here.
admin.site.register(Artist)
admin.site.register(Genre)
admin.site.register(Album)
admin.site.register(Track)
admin.site.register(Contributor)
admin.site.register(PlatformAvailability)
admin.site.register(Fingerprint)
admin.site.register(TrackFeedback)