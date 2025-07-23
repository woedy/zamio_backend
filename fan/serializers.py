from django.contrib.auth import get_user_model
from rest_framework import serializers

from fan.models import Fan


User = get_user_model()




class AllFansSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    registered_on = serializers.SerializerMethodField()


    class Meta:
        model = Fan
        fields = ["fan_id", "username", "photo", "registered_on"]

    def get_photo(self, obj):
        return obj.user.photo.url if obj.user else None

    def get_registered_on(self, obj):
        return obj.user.timestamp if obj.user else None


class FanDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = Fan
        fields = "__all__"


