from rest_framework import serializers

from music_monitor.models import MatchCache, PlayLog, Dispute
from .models import Station, StationProgram, ProgramStaff, StationStaff

# Station Serializer
class AllStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = '__all__'


class StationDetailsSerializer(serializers.ModelSerializer):
    staff_count = serializers.SerializerMethodField()
    stream_links_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Station
        fields = '__all__'
    
    def get_staff_count(self, obj):
        return obj.station_staff.filter(is_archived=False, active=True).count()
    
    def get_stream_links_count(self, obj):
        return obj.station_links.filter(is_archived=False, active=True).count()



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
    status = serializers.SerializerMethodField()

    class Meta:
        model = PlayLog
        fields = [
            'id', 'track_title', 'artist_name', 'start_time', 'stop_time', 'duration',
            'avg_confidence_score', 'royalty_amount', 'flagged', 'status'
        ]


    def get_start_time(self, obj):
        return obj.start_time.strftime('%Y-%m-%d ~ %H:%M:%S')


    def get_stop_time(self, obj):
        return obj.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S')


    def get_duration(self, obj):
        total_seconds = int(obj.duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_status(self, obj):
        # If flagged, show Flagged; else if any related Dispute is Resolved, show Resolved; else blank
        try:
            if getattr(obj, 'flagged', False):
                return 'Flagged'
            # Check for a resolved dispute on this playlog
            if Dispute.objects.filter(playlog=obj, dispute_status='Resolved').exists():
                return 'Resolved'
        except Exception:
            pass
        return ''


class StationMatchCacheSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    artist_name = serializers.CharField(source='track.artist.stage_name', read_only=True)
    matched_at = serializers.SerializerMethodField()

    class Meta:
        model = MatchCache
        fields = ['id', 'track_title', 'artist_name', 'matched_at', 'avg_confidence_score']

    def get_matched_at(self, obj):
        return obj.matched_at.strftime('%Y-%m-%d ~ %H:%M:%S')


class StationStaffSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    
    class Meta:
        model = StationStaff
        fields = [
            'id', 'name', 'email', 'phone', 'role', 'permission_level',
            'emergency_contact', 'emergency_phone', 'hire_date', 'employee_id',
            'department', 'can_upload_playlogs', 'can_manage_streams', 
            'can_view_analytics', 'active', 'station_name', 'created_at'
        ]


class StationStaffDetailsSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    
    class Meta:
        model = StationStaff
        fields = '__all__'


class StationComplianceSerializer(serializers.ModelSerializer):
    """Serializer for compliance-related station information"""
    
    class Meta:
        model = Station
        fields = [
            'station_id', 'name', 'regulatory_body', 'compliance_contact_name',
            'compliance_contact_email', 'compliance_contact_phone', 'license_number',
            'verification_status', 'verified_at', 'verification_notes',
            'station_class', 'station_type', 'coverage_area', 'estimated_listeners'
        ]
