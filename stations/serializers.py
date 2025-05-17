from rest_framework import serializers
from .models import Station, StationProgram, ProgramStaff

# Station Serializer
class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = '__all__'

# Station Program Serializer
class StationProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = StationProgram
        fields = '__all__'

# Program Staff Serializer
class ProgramStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramStaff
        fields = '__all__'
