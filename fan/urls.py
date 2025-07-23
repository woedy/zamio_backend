from django.urls import path

from fan.views import add_fan, archive_fan, edit_fan, get_all_archived_fans_view, get_all_fans_view, get_fan_details_view, unarchive_fan


app_name = "fan"

urlpatterns = [

    # 🎤 Fan
    path('add/', add_fan, name='add_fan'),
    path('get-all-fans/', get_all_fans_view, name='get_all_fans'),
    path('get-fan-details/', get_fan_details_view, name='get_fan_details'),
    path('edit-fan/', edit_fan, name='edit_fan'),
    path('archive-fan/', archive_fan, name='archive_fan'),
    path('unarchive-fan/', unarchive_fan, name='unarchive_fan'),
    # path('delete/', delete_fan, name='delete_fan'),
    path('get-all-archived-fans/', get_all_archived_fans_view, name='archived_fans'),
]