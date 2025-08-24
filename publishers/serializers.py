from django.contrib.auth import get_user_model
from rest_framework import serializers

from music_monitor.models import MatchCache, PlayLog, StreamLog
from .models import PublisherProfile, PublishingAgreement


User = get_user_model()




class AllPublishersSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    registered_on = serializers.SerializerMethodField()


    class Meta:
        model = PublisherProfile
        fields = ["publisher_id", "stage_name","total_earnings", "photo", "registered_on"]

    def get_photo(self, obj):
        return obj.user.photo.url if obj.user else None

    def get_registered_on(self, obj):
        return obj.user.timestamp if obj.user else None


class PublisherDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = PublisherProfile
        fields = "__all__"



class PublisherPlayLogSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    station_name = serializers.CharField(source='station.name', read_only=True)
    start_time = serializers.SerializerMethodField()
    stop_time = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = PlayLog
        fields = ['id', 'track_title', 'station_name', 'start_time', 'stop_time', 'duration', 'avg_confidence_score', 'royalty_amount']


    def get_start_time(self, obj):
        return obj.start_time.strftime('%Y-%m-%d ~ %H:%M:%S')


    def get_stop_time(self, obj):
        return obj.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S') 


    def get_duration(self, obj):
        total_seconds = int(obj.duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"


class PublisherMatchCacheSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    station_name = serializers.CharField(source='station.name', read_only=True)
    matched_at = serializers.SerializerMethodField()

    class Meta:
        model = MatchCache
        fields = ['id', 'track_title', 'station_name', 'matched_at', 'avg_confidence_score']

    def get_matched_at(self, obj):
        return obj.matched_at.strftime('%Y-%m-%d ~ %H:%M:%S')
    





class PublishingAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishingAgreement
        fields = ['id', 'publisher', 'songwriter', 'track', 'writer_share', 'publisher_share', 'contract_file', 'verified_by_admin', 'agreement_date', 'status', 'is_archived', 'active', 'created_at', 'updated_at']
