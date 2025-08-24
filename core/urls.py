from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def health_check(request):
    """Health check endpoint for Coolify"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'Django application is running'
    })

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("api/accounts/", include("accounts.api.urls")),
    path("api/artists/", include("artists.urls")),
    path("api/bank/", include("bank_account.urls")),
    path("api/fan/", include("fan.urls")),
    path("api/mr-admin/", include("mr_admin.urls")),
    path("api/music-monitor/", include("music_monitor.urls")),
    path("api/notifications/", include("notifications.api.urls")),
    path("api/publishers/", include("publishers.urls")),
    path("api/stations/", include("stations.urls")),
    #path("api/streamer/", include("streamer.urls")),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

