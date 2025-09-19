from django.contrib.auth import get_user_model
from rest_framework import serializers

from artists.models import Artist
from music_monitor.models import MatchCache, PlayLog


User = get_user_model()




class AllArtistsSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    registered_on = serializers.SerializerMethodField()


    class Meta:
        model = Artist
        fields = ["artist_id", "stage_name","total_earnings", "photo", "registered_on"]

    def get_photo(self, obj):
        return obj.user.photo.url if obj.user else None

    def get_registered_on(self, obj):
        return obj.user.timestamp if obj.user else None


class ArtistDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = "__all__"



from rest_framework import serializers
from .models import Genre, Album, Track, Contributor, PlatformAvailability

# Genre Serializer
class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name']

# Album Serializer
class AlbumSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source='artist.stage_name', read_only=True)  # Include artist stage name

    class Meta:
        model = Album
        fields = ['id', 'title', 'artist_name']

# Track Serializer
class TrackSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source='artist.stage_name', read_only=True)  # To include artist name in the response
    album_title = serializers.CharField(source='album.title', read_only=True)  # To include album title in the response
    genre_name = serializers.CharField(source='genre.name', read_only=True)  # To include genre name in the response
    airplays = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = '__all__'

    def get_airplays(self, obj):
        return PlayLog.objects.filter(track=obj).count()

    




class TrackDetailsSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source='artist.stage_name', read_only=True)  # To include artist name in the response
    album_title = serializers.CharField(source='album.title', read_only=True)  # To include album title in the response
    genre_name = serializers.CharField(source='genre.name', read_only=True)  # To include genre name in the response

    class Meta:
        model = Track
        fields = '__all__'




# Contributor Serializer
class ContributorSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  # To include track title in the response

    class Meta:
        model = Contributor
        fields = '__all__'

# PlatformAvailability Serializer
class PlatformAvailabilitySerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  # To include track title in the response

    class Meta:
        model = PlatformAvailability
        fields = '__all__'



class ArtistPlayLogSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    station_name = serializers.CharField(source='station.name', read_only=True)
    start_time = serializers.SerializerMethodField()
    stop_time = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    attribution_source = serializers.SerializerMethodField()
    partner_name = serializers.SerializerMethodField()

    class Meta:
        model = PlayLog
        fields = ['id', 'track_title', 'station_name', 'start_time', 'stop_time', 'duration', 'royalty_amount', 'attribution_source', 'partner_name']


    def get_start_time(self, obj):
        return obj.start_time.strftime('%Y-%m-%d ~ %H:%M:%S')


    def get_stop_time(self, obj):
        return obj.stop_time.strftime('%Y-%m-%d ~ %H:%M:%S') 


    def get_duration(self, obj):
        total_seconds = int(obj.duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_attribution_source(self, obj):
        try:
            from royalties.models import UsageAttribution
        except Exception:
            return "Local"
        if UsageAttribution.objects.filter(play_log=obj).exists():
            return "Partner"
        return "Local"

    def get_partner_name(self, obj):
        try:
            from royalties.models import UsageAttribution
        except Exception:
            return None
        ua = UsageAttribution.objects.filter(play_log=obj).select_related('origin_partner').first()
        if ua and ua.origin_partner:
            # Prefer display_name then company_name
            return ua.origin_partner.display_name or ua.origin_partner.company_name
        return None


class ArtistMatchCacheSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source='track.title', read_only=True)  
    station_name = serializers.CharField(source='station.name', read_only=True)
    matched_at = serializers.SerializerMethodField()

    class Meta:
        model = MatchCache
        fields = ['id', 'track_title', 'station_name', 'matched_at']

    def get_matched_at(self, obj):
        return obj.matched_at.strftime('%Y-%m-%d ~ %H:%M:%S')
