# urls.py
from django.urls import path

from music_monitor.views.match_log_views import get_active_sessions, get_stream_matches, start_stream_monitoring, stop_stream_monitoring, upload_audio_match
from music_monitor.views.stram_log import LogStreamView, log_music_play
from music_monitor.views.views import get_matchcache_list, get_playlog_list


app_name = "music_monitor"

urlpatterns = [

    path('stream/upload/', upload_audio_match),

    path('stream/log-play/', log_music_play, name='log_music_play'),
    path('log-stream/', LogStreamView.as_view(), name='log-stream'),

    
    path('stream/start/', start_stream_monitoring, name='start_stream_monitoring'),
    path('stream/stop/<str:session_id>/', stop_stream_monitoring, name='stop_stream_monitoring'),
    path('stream/matches/<str:session_id>/', get_stream_matches, name='get_stream_matches'),
    path('stream/sessions/', get_active_sessions, name='get_active_sessions'),

    # MatchCache
    #path('matchcache/', add_matchcache, name='add_matchcache'),
    path('matchcache/list/', get_matchcache_list, name='get_matchcache_list'),
#
    ## PlayLog
    #path('playlog/', add_playlog, name='add_playlog'),
    path('playlog/list/', get_playlog_list, name='get_playlog_list'),
]
