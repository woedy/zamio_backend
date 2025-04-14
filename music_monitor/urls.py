from django.urls import path
from .views import upload_clip

urlpatterns = [
    path('upload-clip/', upload_clip),
]
