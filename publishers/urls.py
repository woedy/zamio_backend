# publishing/urls.py

from django.urls import path

from publishers.views.managed_artist_views import get_all_managed_artists_view, get_managed_artist_details_view
from publishers.views.publisher_contracts_view import (
    get_all_artist_contracts_view,
    get_contract_detail_view,
    list_tracks_for_artist_view,
    create_publishing_agreement_view,
)
from publishers.views.publisher_royalties_view import (
    get_all_managed_artists_royalties_view,
    get_artist_royalties_detail_view,
)
from publishers.views.publisher_hompage import get_publisher_homedata
from publishers.views.publisher_match_logs import get_all_artist_playlog_for_publisher_view
from publishers.views.publisher_view import get_publisher_profile_view, edit_publisher
from publishers.views.link_artist_views import (
    link_multiple_artists_view,
    search_artists_to_link_view,
    link_artist_to_publisher_view,
    invite_artist_view,
)
from publishers.views.publisher_disputes_view import get_all_publisher_disputes_view


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
    path('playlogs/', get_all_artist_playlog_for_publisher_view, name='get_all_artist_playlog_for_publisher_view'),
    # Royalties endpoints for publisher
    path('royalties/artists/', get_all_managed_artists_royalties_view, name='get_all_managed_artists_royalties_view'),
    path('royalties/artist-details/', get_artist_royalties_detail_view, name='get_artist_royalties_detail_view'),
    path('all-contracts/', get_all_artist_contracts_view, name='get_all_artist_contracts_view'),
    path('contract-details/', get_contract_detail_view, name='get_contract_detail_view'),
    path('artist-tracks/', list_tracks_for_artist_view, name='list_tracks_for_artist_view'),
    path('contracts/create/', create_publishing_agreement_view, name='create_publishing_agreement_view'),
    
    path('publisher-profile/', get_publisher_profile_view, name='get_publisher_profile_view'),
    path('publisher-profile/edit/', edit_publisher, name='edit_publisher'),

    # Onboarding: link or invite artist
    path('link-artist/search/', search_artists_to_link_view, name='search_artists_to_link_view'),
    path('link-artist/link/', link_artist_to_publisher_view, name='link_artist_to_publisher_view'),
    path('link-artist/link-multiple/', link_multiple_artists_view, name='link_multiple_artists_view'),
    path('link-artist/invite/', invite_artist_view, name='invite_artist_view'),

    # Disputes for publishers
    path('disputes/', get_all_publisher_disputes_view, name='get_all_publisher_disputes_view'),
]
