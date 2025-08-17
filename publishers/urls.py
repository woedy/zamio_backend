# publishing/urls.py

from django.urls import path

from publishers.views.managed_artist_views import get_all_managed_artists_view, get_managed_artist_details_view
from publishers.views.publisher_hompage import get_publisher_homedata


app_name = 'publishers'

urlpatterns = [
    #path('assign/<int:song_id>/', assign_existing_publisher, name='assign_publisher'),
#
    #path('publisher/profile/', create_or_update_publisher_profile, name='create_publisher_profile'),
    #path('publisher/dashboard/', publisher_dashboard, name='publisher_dashboard'),
    #path('song/<int:song_id>/invite-publisher/', invite_publisher_to_song, name='invite_publisher'),
    #path('invitation/accept/<uuid:token>/', accept_publisher_invitation, name='accept_publisher_invitation'),
    #path('publisher/agreements/', view_publishing_agreements, name='view_publishing_agreements'),


    path('dashboard/', get_publisher_homedata, name='get_publisher_homedata'),
    path('all-managed-artists/', get_all_managed_artists_view, name='get_all_managed_artists'),
    path('managed-artist-details/', get_managed_artist_details_view, name='get_managed_artist_details_view'),


]
