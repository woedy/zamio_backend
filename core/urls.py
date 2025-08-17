from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.api.urls', 'accounts_api')),
    path('api/artists/', include('artists.urls', 'artists_api')),
    path('api/stations/', include('stations.urls', 'stations_api')),
    path('api/publishers/', include('publishers.urls', 'publishers_api')),
    path('api/fan/', include('fan.urls', 'fan_api')),
    path('api/mr-admin/', include('mr_admin.urls', 'mr_admin_api')),
    path('api/music-monitor/', include('music_monitor.urls', 'music_monitor_api')),
    path('api/bank-account/', include('bank_account.urls', 'bank_account_api')),
    path('api/notifications/', include('notifications.api.urls', 'notifications_api')),
]

#if settings.DEBUG:
#    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
#    # 🚫 Do NOT include media static serving here — MinIO handles that


if settings.DEBUG:
    urlpatterns = urlpatterns + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

