from django.urls import path

from accounts.api.admin_view import AdminLogin, register_admin_view
from accounts.api.artist_views import ArtistLogin, register_artist_view
from accounts.api.chef_views import resend_email_verification, verify_email
from accounts.api.password_views import PasswordResetView, confirm_otp_password_view, new_password_reset_view, resend_password_otp

app_name = 'accounts'

urlpatterns = [
    path('register-admin/', register_admin_view, name="register_admin_view"),
    path('login-admin/', AdminLogin.as_view(), name="login_admin"),
    path('verify-email/', verify_email, name="verify_admin_email"),
    path('resend-email-verification/', resend_email_verification, name="resend_admin_email_verification"),


    path('register-artist/', register_artist_view, name="register_artist"),
    path('login-artist/', ArtistLogin.as_view(), name="login_artist"),
   # 

    #path('register-chef/', register_chef, name="register_chef"),
    #path('login-chef/', ChefLogin.as_view(), name="login_chef"),
    #path('verify-chef-email/', verify_chef_email, name="verify_chef_email"),
    #path('resend-chef-email-verification/', resend_chef_email_verification, name="resend_chef_email_verification"),




    path('forgot-user-password/', PasswordResetView.as_view(), name="forgot_password"),
    path('confirm-password-otp/', confirm_otp_password_view, name="confirm_otp_password"),
    path('resend-password-otp/', resend_password_otp, name="resend_password_otp"),
    path('new-password-reset/', new_password_reset_view, name="new_password_reset_view"),

    #path('remove_user/', remove_user_view, name="remove_user_view"),
   # path('send-sms/', send_sms_view, name="send_sms_view"),

]
