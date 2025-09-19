# urls.py
from django.urls import path

from music_monitor.views.dispute_views import (
    flag_match_for_dispute,
    get_all_station_disputes_view,
    get_all_artist_disputes_view,
    get_match_dispute_details_view,
    review_match_for_dispute,
    get_all_disputes_admin_view,
)
from music_monitor.views.match_log_views import (
    get_active_sessions,
    get_stream_matches,
    start_stream_monitoring,
    stop_stream_monitoring,
    upload_audio_match,
)
from music_monitor.views.stram_log import LogStreamView, log_music_play
from music_monitor.views.views import (
    delete_all_matches,
    get_matchcache_list,
    get_playlog_list,
)
from music_monitor.views.enhanced_fingerprinting_views import (
    fingerprint_track,
    batch_fingerprint_tracks,
    fingerprint_task_status,
    fingerprint_statistics,
    auto_fingerprint_new,
    track_fingerprint_status,
)
from music_monitor.views.acrcloud_views import (
    test_acrcloud_identification,
    test_hybrid_detection,
    lookup_isrc,
    batch_lookup_isrcs,
    get_pro_mappings,
    get_detection_statistics,
    trigger_isrc_update,
    trigger_hybrid_detection_task,
)


app_name = "music_monitor"

urlpatterns = [
    path("stream/upload/", upload_audio_match),
    path("stream/log-play/", log_music_play, name="log_music_play"),
    path("log-stream/", LogStreamView.as_view(), name="log-stream"),
    path("flag-playlog/", flag_match_for_dispute, name="flag_match_for_dispute"),
    path("stream/start/", start_stream_monitoring, name="start_stream_monitoring"),
    path(
        "stream/stop/<str:session_id>/",
        stop_stream_monitoring,
        name="stop_stream_monitoring",
    ),
    path(
        "stream/matches/<str:session_id>/",
        get_stream_matches,
        name="get_stream_matches",
    ),
    path("stream/sessions/", get_active_sessions, name="get_active_sessions"),
    # MatchCache
    # path('matchcache/', add_matchcache, name='add_matchcache'),
    path("matchcache/list/", get_matchcache_list, name="get_matchcache_list"),
    #
    ## PlayLog
    # path('playlog/', add_playlog, name='add_playlog'),
    path("playlog/list/", get_playlog_list, name="get_playlog_list"),
    path("delete-all-matches/", delete_all_matches, name="delete_all_items"),

    path("stations-match-disputes/", get_all_station_disputes_view, name="get_all_station_disputes_view"),
    path("artist-disputes/", get_all_artist_disputes_view, name="get_all_artist_disputes_view"),
    path("disputes/", get_all_disputes_admin_view, name="get_all_disputes_admin_view"),
    path("match-dispute-details/", get_match_dispute_details_view, name="get_match_dispute_details_view"),
    path("review-match-for-dispute/", review_match_for_dispute, name="review_match_for_dispute"),
    
    # Enhanced Fingerprinting Endpoints
    path("fingerprint/track/", fingerprint_track, name="fingerprint_track"),
    path("fingerprint/batch/", batch_fingerprint_tracks, name="batch_fingerprint_tracks"),
    path("fingerprint/task/<str:task_id>/", fingerprint_task_status, name="fingerprint_task_status"),
    path("fingerprint/stats/", fingerprint_statistics, name="fingerprint_statistics"),
    path("fingerprint/auto/", auto_fingerprint_new, name="auto_fingerprint_new"),
    path("fingerprint/track/<int:track_id>/status/", track_fingerprint_status, name="track_fingerprint_status"),
    
    # ACRCloud Integration Endpoints
    path("acrcloud/test-identification/", test_acrcloud_identification, name="test_acrcloud_identification"),
    path("acrcloud/test-hybrid/", test_hybrid_detection, name="test_hybrid_detection"),
    path("acrcloud/isrc/<str:isrc>/", lookup_isrc, name="lookup_isrc"),
    path("acrcloud/batch-isrc/", batch_lookup_isrcs, name="batch_lookup_isrcs"),
    path("acrcloud/pro-mappings/", get_pro_mappings, name="get_pro_mappings"),
    path("acrcloud/statistics/", get_detection_statistics, name="get_detection_statistics"),
    path("acrcloud/update-isrc/<str:isrc>/", trigger_isrc_update, name="trigger_isrc_update"),
    path("acrcloud/hybrid-task/", trigger_hybrid_detection_task, name="trigger_hybrid_detection_task"),
]
