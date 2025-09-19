from django.urls import path

from stations.views.station_dashboard_view import get_station_dashboard_data
from stations.views.station_playlog_views import get_all_station_playlog_view
from stations.views.station_programs_staff_views import add_program_staff, archive_program_staff, delete_program_staff, edit_program_staff, get_all_archived_program_staff_view, get_all_program_staff_view, get_program_staff_details_view, unarchive_program_staff
from stations.views.station_programs_views import add_station_program, archive_station_program, delete_station_program, edit_station_program, get_all_archived_station_programs_view, get_all_station_programs_view, get_station_program_details_view, unarchive_station_program
from stations.views.station_views import archive_station, edit_station, get_all_archived_stations_view, get_all_stations_view, get_station_details_view, unarchive_station
from stations.views.station_stream_links_views import (
    get_station_stream_links_view,
    add_station_stream_link_view,
    edit_station_stream_link_view,
    delete_station_stream_link_view,
)
from stations.views.station_staff_views import (
    add_station_staff,
    get_station_staff_list,
    get_station_staff_details,
    edit_station_staff,
    archive_station_staff,
    activate_station_staff,
)
from stations.views.station_compliance_views import (
    update_station_compliance,
    get_stations_for_verification,
    verify_station,
    get_station_compliance_report,
)
from stations.views.playlog_management_views import (
    upload_playlog,
    get_playlog_comparison,
    get_match_log_details,
    verify_detection_match,
)
from . import views

app_name = "stations"

urlpatterns = [
    # Station URLs
    # path('add/', add_station, name='add_station'),
    path('get-all-stations/', get_all_stations_view, name='get_all_stations'),
    path('get-station-details/', get_station_details_view, name='get_station_details'),
    path('edit-station/', edit_station, name='edit_station'),
    path('archive-station/', archive_station, name='archive_station'),
    path('unarchive-station/', unarchive_station, name='unarchive_station'),
    # path('delete/', delete_station, name='delete_station'),
    path('get-all-archived-stations/', get_all_archived_stations_view, name='get_all_archived_stations'),
# 
    # # StationProgram URLs
    path('add-station-program/', add_station_program, name='add_station_program'),
    path('get-all-station-programs/', get_all_station_programs_view, name='get_all_station_programs'),
    path('get-station-program-details/', get_station_program_details_view, name='get_station_program_details'),
    path('edit-station-program/', edit_station_program, name='edit_station_program'),
    path('archive-station-program/', archive_station_program, name='archive_station_program'),
    path('unarchive-station-program/', unarchive_station_program, name='unarchive_station_program'),
    path('delete-station-program/', delete_station_program, name='delete_station_program'),
    path('get-all-archived-station-programs/', get_all_archived_station_programs_view, name='get_all_archived_station_programs'),
# 
    # # ProgramStaff URLs
    path('add-program-staff/', add_program_staff, name='add_program_staff'),
    path('get-all-program-staffs/', get_all_program_staff_view, name='get_all_program_staff'),
    path('get-program-staff-details/', get_program_staff_details_view, name='get_program_staff_details'),
    path('edit-program-staff/', edit_program_staff, name='edit_program_staff'),
    path('archive-program-staff/', archive_program_staff, name='archive_program_staff'),
    path('unarchive-program-staff/', unarchive_program_staff, name='unarchive_program_staff'),
    path('delete-program-staff/', delete_program_staff, name='delete_program_staff'),
    path('get-all-archived-program-staff/', get_all_archived_program_staff_view, name='get_all_archived_program_staff'),
    
    path('dashboard/', get_station_dashboard_data, name='get_station_dashboard_data'),
    path('playlogs/', get_all_station_playlog_view, name='get_all_station_playlog_view'),

    # Station Stream Links
    path('get-station-stream-links/', get_station_stream_links_view, name='get_station_stream_links_view'),
    path('add-station-stream-link/', add_station_stream_link_view, name='add_station_stream_link_view'),
    path('edit-station-stream-link/', edit_station_stream_link_view, name='edit_station_stream_link_view'),
    path('delete-station-stream-link/', delete_station_stream_link_view, name='delete_station_stream_link_view'),

    # Station Staff Management
    path('add-station-staff/', add_station_staff, name='add_station_staff'),
    path('get-station-staff-list/', get_station_staff_list, name='get_station_staff_list'),
    path('get-station-staff-details/', get_station_staff_details, name='get_station_staff_details'),
    path('edit-station-staff/', edit_station_staff, name='edit_station_staff'),
    path('archive-station-staff/', archive_station_staff, name='archive_station_staff'),
    path('activate-station-staff/', activate_station_staff, name='activate_station_staff'),

    # Station Compliance and Verification
    path('update-station-compliance/', update_station_compliance, name='update_station_compliance'),
    path('get-stations-for-verification/', get_stations_for_verification, name='get_stations_for_verification'),
    path('verify-station/', verify_station, name='verify_station'),
    path('get-station-compliance-report/', get_station_compliance_report, name='get_station_compliance_report'),

    # Playlog and Match Log Management
    path('upload-playlog/', upload_playlog, name='upload_playlog'),
    path('get-playlog-comparison/', get_playlog_comparison, name='get_playlog_comparison'),
    path('get-match-log-details/', get_match_log_details, name='get_match_log_details'),
    path('verify-detection-match/', verify_detection_match, name='verify_detection_match'),

]
