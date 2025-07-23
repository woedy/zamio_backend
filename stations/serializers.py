from rest_framework import serializers

from music_monitor.models import MatchCache, PlayLog
from .models import Station, StationProgram, ProgramStaff

# Station Serializer
class AllStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = '__all__'


class StationDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = '__all__'



# Station Program Serializer
class AllStationProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = StationProgram
        fields = '__all__'

class StationProgramDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StationProgram
        fields = '__all__'


# Program Staff Serializer
class ProgramStaffDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramStaff
        fields = '__all__'

class ProgramStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramStaff
        fields = '__all__'





class StationPlayLogSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    artist_name = serializers.CharField(source='track.artist.stage_name', read_only=True)
    start_time = serializers.SerializerMethodField()
    stop_time = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = PlayLog
        fields = ['id', 'track_title', 'artist_name', 'start_time', 'stop_time', 'duration', 'avg_confidence_score', 'royalty_amount', 'flagged']


    def get_start_time(self, obj):
        return obj.start_time.strftime('%Y-%m-%d ~ %H:%M:%S')


    def get_stop_time(self, obj):
        return obj.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S')


    def get_duration(self, obj):
        total_seconds = int(obj.duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"


class StationMatchCacheSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    artist_name = serializers.CharField(source='track.artist.stage_name', read_only=True)
    matched_at = serializers.SerializerMethodField()

    class Meta:
        model = MatchCache
        fields = ['id', 'track_title', 'artist_name', 'matched_at', 'avg_confidence_score']

    def get_matched_at(self, obj):
        return obj.matched_at.strftime('%Y-%m-%d ~ %H:%M:%S')