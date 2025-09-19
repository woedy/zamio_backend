from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/analytics/', consumers.AnalyticsConsumer.as_asgi()),
    path('ws/analytics/realtime/', consumers.RealtimeMetricsConsumer.as_asgi()),
]