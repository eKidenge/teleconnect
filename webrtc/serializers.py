from rest_framework import serializers
from django.contrib.auth.models import User
from .models import WebRTCCall, CallSignal, PeerConnection

# Create a simple User serializer since we don't have users app
class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class WebRTCCallSerializer(serializers.ModelSerializer):
    caller = SimpleUserSerializer(read_only=True)
    callee = SimpleUserSerializer(read_only=True)
    
    class Meta:
        model = WebRTCCall
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'last_activity']

class CallSignalSerializer(serializers.ModelSerializer):
    sender = SimpleUserSerializer(read_only=True)
    
    class Meta:
        model = CallSignal
        fields = '__all__'
        read_only_fields = ['sender', 'created_at']

class PeerConnectionSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)
    
    class Meta:
        model = PeerConnection
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

# All serializers that views.py needs
class CreateCallSerializer(serializers.Serializer):
    callee_id = serializers.IntegerField(required=True)
    call_type = serializers.ChoiceField(choices=['audio', 'video', 'screen'], default='video')
    room_name = serializers.CharField(required=False, allow_null=True)

class CreateOfferSerializer(serializers.Serializer):
    callee_id = serializers.IntegerField(required=True)
    call_type = serializers.ChoiceField(choices=['audio', 'video', 'screen'], default='video')
    offer = serializers.JSONField(required=True)

class CreateAnswerSerializer(serializers.Serializer):
    call_id = serializers.CharField(required=True)
    answer = serializers.JSONField(required=True)

class ICECandidateSerializer(serializers.Serializer):
    call_id = serializers.CharField(required=True)
    candidate = serializers.JSONField(required=True)

class CallStatusUpdateSerializer(serializers.Serializer):
    call_id = serializers.CharField(required=True)
    status = serializers.ChoiceField(choices=['accepted', 'rejected', 'ended', 'cancelled'])

class OfferSerializer(serializers.Serializer):
    call_id = serializers.CharField(required=True)
    offer = serializers.JSONField(required=True)

class AnswerSerializer(serializers.Serializer):
    call_id = serializers.CharField(required=True)
    answer = serializers.JSONField(required=True)

class HangupSerializer(serializers.Serializer):
    call_id = serializers.CharField(required=True)
