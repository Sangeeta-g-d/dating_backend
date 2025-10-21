from rest_framework import serializers
from .models import Swipe, Match
from django.conf import settings

User = settings.AUTH_USER_MODEL

class SwipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Swipe
        fields = ['id', 'from_user', 'to_user', 'is_liked', 'created_at']
        

class MatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = ['id', 'user1', 'user2', 'matched_at']
