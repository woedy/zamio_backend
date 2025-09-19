from django.urls import path, include
from . import views

app_name = 'analytics'

urlpatterns = [
    # Analytics data endpoints
    path('artist/', views.artist_analytics, name='artist_analytics'),
    path('artist/<str:artist_id>/', views.artist_analytics, name='artist_analytics_by_id'),
    
    path('publisher/', views.publisher_analytics, name='publisher_analytics'),
    path('publisher/<int:publisher_id>/', views.publisher_analytics, name='publisher_analytics_by_id'),
    
    path('station/', views.station_analytics, name='station_analytics'),
    path('station/<str:station_id>/', views.station_analytics, name='station_analytics_by_id'),
    
    path('admin/', views.admin_analytics, name='admin_analytics'),
    
    # Real-time metrics
    path('realtime/', views.realtime_metrics, name='realtime_metrics'),
    
    # Export functionality
    path('export/request/', views.request_export, name='request_export'),
    path('export/<uuid:export_id>/status/', views.export_status, name='export_status'),
    path('export/<uuid:export_id>/download/', views.download_export, name='download_export'),
    
    # User preferences
    path('preferences/', views.user_preferences, name='user_preferences'),
    
    # Comparative analytics
    path('comparative/', views.comparative_analytics, name='comparative_analytics'),
]