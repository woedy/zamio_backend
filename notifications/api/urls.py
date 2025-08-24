from django.urls import path

from notifications.api.views import get_all_artist_notifications_view, get_all_publisher_notifications_view, get_all_station_notifications_view, set_notification_to_read, get_all_notifications, delete_notification

app_name = 'notifications'

urlpatterns = [
        path('get-all-artist-notifications/', get_all_artist_notifications_view, name="get_all_artist_notifications_view"),
        path('get-all-station-notifications/', get_all_station_notifications_view, name="get_all_station_notifications_view"),
        path('get-all-publisher-notifications/', get_all_publisher_notifications_view, name="get_all_publisher_notifications_view"),

    path('set-to-read/', set_notification_to_read, name="set_notification_to_read"),
    path('get-all-notifications/', get_all_notifications, name="get_all_notifications"),
    path('delete-notification/', delete_notification, name="delete_notification"),

]
