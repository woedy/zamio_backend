from django.urls import path

from accounts.api.admin_view import (
    AdminLogin,
    register_admin_view,
    resend_email_verification,
    verify_admin_email,
    admin_onboarding_status_view,
    complete_admin_profile_view,
)
from accounts.api.artist_views import ArtistLogin, complete_artist_payment_view, complete_artist_profile_view, complete_artist_publisher_view, complete_artist_social_view, logout_artist_view, register_artist_view, verify_artist_email, onboard_artist_view, skip_artist_onboarding_view
from accounts.api.fan_views import FanLogin, register_fan_view
from accounts.api.publisher_view import PublisherLogin, complete_link_artist_view, complete_publisher_payment_view, complete_publisher_profile_view, complete_revenue_split_view, logout_publisher_view, onboard_publisher_view, register_publisher_view, verify_publisher_email, list_publishers_view, invite_artist_view, skip_publisher_onboarding_view
from accounts.api.station_views import StationLogin, complete_add_staff_view, complete_station_payment_view, complete_station_profile_view, logout_station_view, register_station_view, verify_station_email, onboard_station_view, skip_station_onboarding_view, station_onboarding_status_view
from accounts.api.password_views import PasswordResetView, confirm_otp_password_view, new_password_reset_view, resend_password_otp

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

   # 

    path('register-station/', register_station_view, name="register_station"),
    path('verify-station-email/', verify_station_email, name="verify_station_email"),

    path('login-station/', StationLogin.as_view(), name="login_station"),
    path('station-onboarding/', onboard_station_view, name="onboard_station_view"),
    path('station-onboarding-status/', station_onboarding_status_view, name="station_onboarding_status_view"),
    path('skip-station-onboarding/', skip_station_onboarding_view, name="skip_station_onboarding_view"),
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

   
    path('publisher-onboarding/', onboard_publisher_view, name="onboard_publisher_view"),


    ## Add fan account URL
    path('register-fan/', register_fan_view, name="register_fan"),
    path('login-fan/', FanLogin.as_view(), name="login_fan"),




    path('forgot-user-password/', PasswordResetView.as_view(), name="forgot_password"),
    path('confirm-password-otp/', confirm_otp_password_view, name="confirm_otp_password"),
    path('resend-password-otp/', resend_password_otp, name="resend_password_otp"),
    path('new-password-reset/', new_password_reset_view, name="new_password_reset_view"),

    #path('remove_user/', remove_user_view, name="remove_user_view"),
   # path('send-sms/', send_sms_view, name="send_sms_view"),

]
