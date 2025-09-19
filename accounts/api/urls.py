from django.urls import path

from accounts.api.admin_view import (
    AdminLogin,
    register_admin_view,
    resend_email_verification,
    verify_admin_email,
    admin_onboarding_status_view,
    complete_admin_profile_view,
)
from accounts.api.artist_views import (
    ArtistLogin, complete_artist_payment_view, complete_artist_profile_view, 
    complete_artist_publisher_view, complete_artist_social_view, logout_artist_view, 
    register_artist_view, verify_artist_email, onboard_artist_view, skip_artist_onboarding_view,
    artist_onboarding_status_view, update_onboarding_status_view, complete_artist_onboarding_view,
    set_self_published_status_view, upload_kyc_documents_view
)
from accounts.api.fan_views import FanLogin, register_fan_view
from accounts.api.publisher_view import (
    PublisherLogin, complete_link_artist_view, complete_publisher_payment_view, 
    complete_publisher_profile_view, complete_revenue_split_view, logout_publisher_view, 
    onboard_publisher_view, register_publisher_view, verify_publisher_email, 
    list_publishers_view, invite_artist_view, skip_publisher_onboarding_view,
    publisher_onboarding_status_view, update_publisher_onboarding_status_view,
    complete_publisher_onboarding_view, create_artist_relationship_view
)
from accounts.api.station_views import (
    StationLogin, complete_add_staff_view, complete_station_payment_view, 
    complete_station_profile_view, logout_station_view, register_station_view, 
    verify_station_email, onboard_station_view, skip_station_onboarding_view, 
    station_onboarding_status_view, enhanced_station_onboarding_status_view,
    update_station_onboarding_status_view, complete_station_onboarding_view,
    update_station_stream_links_view, update_station_compliance_setup_view
)
from accounts.api.password_views import PasswordResetView, confirm_otp_password_view, new_password_reset_view, resend_password_otp
from accounts.api.rbac_views import (
    artist_only_view,
    publisher_only_view,
    admin_only_view,
    upload_music_view,
    kyc_required_view,
    user_permissions_view,
    grant_permission_view,
    revoke_permission_view,
    audit_logs_view
)
from accounts.api.user_management_views import (
    get_user_management_overview,
    get_all_users,
    get_user_details,
    update_kyc_status,
    update_user_status,
    bulk_user_operations,
    get_kyc_pending_users
)

app_name = 'accounts'

urlpatterns = [
    path('register-admin/', register_admin_view, name="register_admin_view"),
    path('login-admin/', AdminLogin.as_view(), name="login_admin"),
    path('verify-admin-email/', verify_admin_email, name="verify_admin_email"),
    path('admin-onboarding-status/', admin_onboarding_status_view, name="admin_onboarding_status_view"),
    path('complete-admin-profile/', complete_admin_profile_view, name="complete_admin_profile_view"),

    path('resend-email-verification/', resend_email_verification, name="resend_admin_email_verification"),


    path('register-artist/', register_artist_view, name="register_artist"),
     path('verify-artist-email/', verify_artist_email, name="verify_artist_email"),
    path('login-artist/', ArtistLogin.as_view(), name="login_artist"),
    path('logout-artist/', logout_artist_view, name="logout_artist_view"),
    path('complete-artist-profile/', complete_artist_profile_view, name="complete_artist_profile_view"),
    path('complete-artist-social/', complete_artist_social_view, name="complete_artist_social_view"),
    path('complete-artist-payment/', complete_artist_payment_view, name="complete_artist_payment_view"),
    path('complete-artist-publisher/', complete_artist_publisher_view, name="complete_artist_publisher_view"),
    path('artist-onboarding/', onboard_artist_view, name="onboard_artist_view"),
    path('skip-artist-onboarding/', skip_artist_onboarding_view, name="skip_artist_onboarding_view"),
    
    # Enhanced Artist Onboarding Endpoints
    path('artist-onboarding-status/<str:artist_id>/', artist_onboarding_status_view, name="artist_onboarding_status_view"),
    path('update-onboarding-status/', update_onboarding_status_view, name="update_onboarding_status_view"),
    path('complete-artist-onboarding/', complete_artist_onboarding_view, name="complete_artist_onboarding_view"),
    path('set-self-published-status/', set_self_published_status_view, name="set_self_published_status_view"),
    path('upload-kyc-documents/', upload_kyc_documents_view, name="upload_kyc_documents_view"),

   # 

    path('register-station/', register_station_view, name="register_station"),
    path('verify-station-email/', verify_station_email, name="verify_station_email"),

    path('login-station/', StationLogin.as_view(), name="login_station"),
    path('station-onboarding/', onboard_station_view, name="onboard_station_view"),
    path('station-onboarding-status/', station_onboarding_status_view, name="station_onboarding_status_view"),
    path('skip-station-onboarding/', skip_station_onboarding_view, name="skip_station_onboarding_view"),
    
    # Enhanced Station Onboarding Endpoints
    path('enhanced-station-onboarding-status/<str:station_id>/', enhanced_station_onboarding_status_view, name="enhanced_station_onboarding_status_view"),
    path('update-station-onboarding-status/', update_station_onboarding_status_view, name="update_station_onboarding_status_view"),
    path('complete-station-onboarding/', complete_station_onboarding_view, name="complete_station_onboarding_view"),
    path('update-station-stream-links/', update_station_stream_links_view, name="update_station_stream_links_view"),
    path('update-station-compliance-setup/', update_station_compliance_setup_view, name="update_station_compliance_setup_view"),
    path('logout-station/', logout_station_view, name="logout_station_view"),
    path('complete-station-profile/', complete_station_profile_view, name="complete_station_profile_view"),
    path('complete-add-staff/', complete_add_staff_view, name="complete_add_staff_view"),
    path('complete-station-payment/', complete_station_payment_view, name="complete_station_payment_view"),

    path('register-publisher/', register_publisher_view, name="register_publisher"),
       path('verify-publisher-email/', verify_publisher_email, name="verify_publisher_email"),

    path('login-publisher/', PublisherLogin.as_view(), name="login_publisher"),
    path('list-publishers/', list_publishers_view, name="list_publishers_view"),
    path('logout-publisher/', logout_publisher_view, name="logout_publisher_view"),
    path('complete-publisher-profile/', complete_publisher_profile_view, name="complete_publisher_profile_view"),
    path('complete-revenue-split/', complete_revenue_split_view, name="complete_publisher_profile_view"),
    path('complete-link-artist/', complete_link_artist_view, name="complete_link_artist_view"),
    path('invite-artist/', invite_artist_view, name="invite_artist_view"),
    path('complete-publisher-payment/', complete_publisher_payment_view, name="complete_publisher_payment_view"),
    path('skip-publisher-onboarding/', skip_publisher_onboarding_view, name="skip_publisher_onboarding_view"),
    
    # Enhanced Publisher Onboarding Endpoints
    path('publisher-onboarding-status/<str:publisher_id>/', publisher_onboarding_status_view, name="publisher_onboarding_status_view"),
    path('update-publisher-onboarding-status/', update_publisher_onboarding_status_view, name="update_publisher_onboarding_status_view"),
    path('complete-publisher-onboarding/', complete_publisher_onboarding_view, name="complete_publisher_onboarding_view"),
    path('create-artist-relationship/', create_artist_relationship_view, name="create_artist_relationship_view"),

   
    path('publisher-onboarding/', onboard_publisher_view, name="onboard_publisher_view"),


    ## Add fan account URL
    path('register-fan/', register_fan_view, name="register_fan"),
    path('login-fan/', FanLogin.as_view(), name="login_fan"),




    path('forgot-user-password/', PasswordResetView.as_view(), name="forgot_password"),
    path('confirm-password-otp/', confirm_otp_password_view, name="confirm_otp_password"),
    path('resend-password-otp/', resend_password_otp, name="resend_password_otp"),
    path('new-password-reset/', new_password_reset_view, name="new_password_reset_view"),

    # RBAC Demo Endpoints
    path('rbac/artist-only/', artist_only_view, name="artist_only_view"),
    path('rbac/publisher-only/', publisher_only_view, name="publisher_only_view"),
    path('rbac/admin-only/', admin_only_view, name="admin_only_view"),
    path('rbac/upload-music/', upload_music_view, name="upload_music_view"),
    path('rbac/kyc-required/', kyc_required_view, name="kyc_required_view"),
    path('rbac/user-permissions/', user_permissions_view, name="user_permissions_view"),
    path('rbac/grant-permission/', grant_permission_view, name="grant_permission_view"),
    path('rbac/revoke-permission/', revoke_permission_view, name="revoke_permission_view"),
    path('rbac/audit-logs/', audit_logs_view, name="audit_logs_view"),

    # User Management Endpoints
    path('admin/user-management-overview/', get_user_management_overview, name="get_user_management_overview"),
    path('admin/all-users/', get_all_users, name="get_all_users"),
    path('admin/user-details/', get_user_details, name="get_user_details"),
    path('admin/update-kyc-status/', update_kyc_status, name="update_kyc_status"),
    path('admin/update-user-status/', update_user_status, name="update_user_status"),
    path('admin/bulk-user-operations/', bulk_user_operations, name="bulk_user_operations"),
    path('admin/kyc-pending-users/', get_kyc_pending_users, name="get_kyc_pending_users"),

    #path('remove_user/', remove_user_view, name="remove_user_view"),
   # path('send-sms/', send_sms_view, name="send_sms_view"),

]
