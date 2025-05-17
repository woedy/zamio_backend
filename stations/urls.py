from django.urls import path
from . import views

urlpatterns = [
    # Station URLs
    path('stations/add/', views.add_station, name='add_station'),
    path('stations/all/', views.get_all_stations_view, name='get_all_stations'),
    path('stations/details/', views.get_station_details_view, name='get_station_details'),
    path('stations/edit/', views.edit_station, name='edit_station'),
    path('stations/archive/', views.archive_station, name='archive_station'),
    path('stations/unarchive/', views.unarchive_station, name='unarchive_station'),
    path('stations/delete/', views.delete_station, name='delete_station'),
    path('stations/archived/', views.get_all_archived_stations_view, name='get_all_archived_stations'),

    # StationProgram URLs
    path('station-programs/add/', views.add_station_program, name='add_station_program'),
    path('station-programs/all/', views.get_all_station_programs_view, name='get_all_station_programs'),
    path('station-programs/details/', views.get_station_program_details_view, name='get_station_program_details'),
    path('station-programs/edit/', views.edit_station_program, name='edit_station_program'),
    path('station-programs/archive/', views.archive_station_program, name='archive_station_program'),
    path('station-programs/unarchive/', views.unarchive_station_program, name='unarchive_station_program'),
    path('station-programs/delete/', views.delete_station_program, name='delete_station_program'),
    path('station-programs/archived/', views.get_all_archived_station_programs_view, name='get_all_archived_station_programs'),

    # ProgramStaff URLs
    path('program-staff/add/', views.add_program_staff, name='add_program_staff'),
    path('program-staff/all/', views.get_all_program_staff_view, name='get_all_program_staff'),
    path('program-staff/details/', views.get_program_staff_details_view, name='get_program_staff_details'),
    path('program-staff/edit/', views.edit_program_staff, name='edit_program_staff'),
    path('program-staff/archive/', views.archive_program_staff, name='archive_program_staff'),
    path('program-staff/unarchive/', views.unarchive_program_staff, name='unarchive_program_staff'),
    path('program-staff/delete/', views.delete_program_staff, name='delete_program_staff'),
    path('program-staff/archived/', views.get_all_archived_program_staff_view, name='get_all_archived_program_staff'),
]
