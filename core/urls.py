from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .view import home_page
from accounts.api.custom_jwt import CustomTokenObtainPairView, CustomTokenRefreshView, CustomTokenVerifyView
from .api_views import (
    log_frontend_error, 
    health_check as api_health_check, 
    get_error_by_trace_id, 
    get_error_metrics
)

@csrf_exempt
def health_check(request):
    """Health check endpoint for Coolify"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'Django application is running'
    })

urlpatterns = [
    path("", home_page, name="home"),  # Home page
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    
    # JWT Authentication endpoints
    path("api/auth/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", CustomTokenVerifyView.as_view(), name="token_verify"),
    
    # Error logging and monitoring endpoints
    path("api/errors/log/", log_frontend_error, name="log_frontend_error"),
    path("api/errors/<str:trace_id>/", get_error_by_trace_id, name="get_error_by_trace_id"),
    path("api/errors/metrics/", get_error_metrics, name="get_error_metrics"),
    path("api/health/", api_health_check, name="api_health_check"),
    
    path("api/accounts/", include("accounts.api.urls")),
    path("api/artists/", include("artists.urls")),
    path("api/bank/", include("bank_account.urls")),
    path("api/fan/", include("fan.urls")),
    path("api/mr-admin/", include("mr_admin.urls")),
    path("api/music-monitor/", include("music_monitor.urls")),
    path("api/notifications/", include("notifications.api.urls")),
    path("api/publishers/", include("publishers.urls")),
    path("api/stations/", include("stations.urls")),
    path("api/royalties/", include("royalties.urls")),
    path("api/disputes/", include("disputes.urls")),
    #path("api/streamer/", include("streamer.urls")),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

