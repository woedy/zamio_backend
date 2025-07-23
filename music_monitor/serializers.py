# serializers.py
from rest_framework import serializers
from .models import Dispute, MatchCache, PlayLog, Track








class MatchCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchCache
        fields = '__all__'




class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = '__all__'

class PlayLogSerializer(serializers.ModelSerializer):
    track = TrackSerializer()
    
    class Meta:
        model = PlayLog
        fields = '__all__'





class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = '__all__'
