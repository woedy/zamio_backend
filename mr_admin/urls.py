from django.urls import path

from mr_admin.views import get_admin_dashboard_data


app_name = "mr_admin"

urlpatterns = [
    path('dashboard/', get_admin_dashboard_data, name='get_admin_dashboard_data'),
]
