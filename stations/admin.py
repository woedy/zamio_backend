from django.contrib import admin

from stations.models import ProgramStaff, Station, StationProgram

# Register your models here.
admin.site.register(Station)
admin.site.register(StationProgram)
admin.site.register(ProgramStaff)
