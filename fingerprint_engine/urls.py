from django.urls import path

urlpatterns = [
    path('upload/', upload_song, name='upload_song'),
    path('detect-audio-match/', upload_song, name='upload_song'),
    path('match/', identify_audio, name='identify_audio'),
]
