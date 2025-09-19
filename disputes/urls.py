from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DisputeViewSet, DisputeNotificationViewSet

app_name = 'disputes'

router = DefaultRouter()
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'notifications', DisputeNotificationViewSet, basename='notification')

urlpatterns = [
    path('api/', include(router.urls)),
]