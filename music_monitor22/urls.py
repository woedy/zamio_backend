# urls.py
from django.urls import path

from fingerprint_engine.views import detect_audio_match, upload_audio_api

#from .views import recent_plays, play_count_per_artist, stations_list

app_name = "music_monitor22"

urlpatterns = [

    path('upload/', upload_audio_api, name='upload_audio_api'),
    path('detect-audio-match/', detect_audio_match, name='detect_audio_match_api'),

    #path('api/audio-snippet/', recent_plays),
    #path('api/recent-plays/', recent_plays),
    #path('api/royalty-summary/', play_count_per_artist),
    #path('api/stations/', stations_list),


      # MatchCache
    #path('matchcache/', views.add_matchcache, name='add_matchcache'),
    #path('matchcache/list/', views.get_matchcache_list, name='get_matchcache_list'),
#
    ## PlayLog
    #path('playlog/', views.add_playlog, name='add_playlog'),
    #path('playlog/list/', views.get_playlog_list, name='get_playlog_list'),
]
