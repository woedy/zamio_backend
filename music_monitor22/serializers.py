# serializers.py
from rest_framework import serializers
from .models import PlayLog, Track, Artist, Station

class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = '__all__'

class PlayLogSerializer(serializers.ModelSerializer):
    track = TrackSerializer()
    
    class Meta:
        model = PlayLog
        fields = '__all__'

class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = '__all__'

class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = '__all__'
