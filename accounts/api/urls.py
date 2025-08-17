from django.urls import path

from accounts.api.admin_view import AdminLogin, register_admin_view, resend_email_verification
from accounts.api.artist_views import ArtistLogin, complete_artist_payment_view, complete_artist_profile_view, complete_artist_publisher_view, complete_artist_social_view, logout_artist_view, register_artist_view, verify_artist_email
from accounts.api.fan_views import FanLogin, register_fan_view
from accounts.api.publisher_view import PublisherLogin, complete_link_artist_view, complete_publisher_payment_view, complete_publisher_profile_view, complete_revenue_split_view, logout_publisher_view, onboard_publisher_view, register_publisher_view, verify_publisher_email
from accounts.api.station_views import StationLogin, complete_add_staff_view, complete_report_method_view, complete_station_payment_view, complete_station_profile_view, logout_station_view, register_station_view, verify_station_email
from accounts.api.password_views import PasswordResetView, confirm_otp_password_view, new_password_reset_view, resend_password_otp

app_name = 'accounts'

urlpatterns = [
    path('register-admin/', register_admin_view, name="register_admin_view"),
    path('login-admin/', AdminLogin.as_view(), name="login_admin"),
   
    path('resend-email-verification/', resend_email_verification, name="resend_admin_email_verification"),


    path('register-artist/', register_artist_view, name="register_artist"),
     path('verify-artist-email/', verify_artist_email, name="verify_artist_email"),
    path('login-artist/', ArtistLogin.as_view(), name="login_artist"),
    path('logout-artist/', logout_artist_view, name="logout_artist_view"),
    path('complete-artist-profile/', complete_artist_profile_view, name="complete_artist_profile_view"),
    path('complete-artist-social/', complete_artist_social_view, name="complete_artist_social_view"),
    path('complete-artist-payment/', complete_artist_payment_view, name="complete_artist_payment_view"),
    path('complete-artist-publisher/', complete_artist_publisher_view, name="complete_artist_publisher_view"),
    path('artist-onboarding/', onboard_publisher_view, name="onboard_publisher_view"),

   # 

    path('register-station/', register_station_view, name="register_station"),
    path('verify-station-email/', verify_station_email, name="verify_station_email"),

    path('login-station/', StationLogin.as_view(), name="login_station"),
    path('station-onboarding/', onboard_publisher_view, name="onboard_publisher_view"),
    path('logout-station/', logout_station_view, name="logout_station_view"),
    path('complete-station-profile/', complete_station_profile_view, name="complete_station_profile_view"),
    path('complete-add-staff/', complete_add_staff_view, name="complete_add_staff_view"),
    path('complete-report-method/', complete_report_method_view, name="complete_report_method_view"),
    path('complete-station-payment/', complete_station_payment_view, name="complete_station_payment_view"),

    path('register-publisher/', register_publisher_view, name="register_publisher"),
       path('verify-publisher-email/', verify_publisher_email, name="verify_publisher_email"),

    path('login-publisher/', PublisherLogin.as_view(), name="login_publisher"),
    path('logout-publisher/', logout_publisher_view, name="logout_publisher_view"),
    path('complete-publisher-profile/', complete_publisher_profile_view, name="complete_publisher_profile_view"),
    path('complete-revenue-split/', complete_revenue_split_view, name="complete_publisher_profile_view"),
    path('complete-link-artist/', complete_link_artist_view, name="complete_link_artist_view"),
    path('complete-publisher-payment/', complete_publisher_payment_view, name="complete_publisher_payment_view"),

   
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
