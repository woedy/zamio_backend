from django.contrib.auth import get_user_model
from rest_framework import serializers

from artists.models import Artist


User = get_user_model()




class ArtistSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = "__all__"



from rest_framework import serializers
from .models import Genre, Album, Track, Contributor, PlatformAvailability

# Genre Serializer
class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = '__all__'

# Album Serializer
class AlbumSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source='artist.name', read_only=True)  # To include artist name in the response

    class Meta:
        model = Album
        fields = '__all__'

# Track Serializer
class TrackSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source='artist.name', read_only=True)  # To include artist name in the response
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
