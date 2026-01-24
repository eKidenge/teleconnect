from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CallRoom, CallParticipant, CallHistory

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class CallParticipantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = CallParticipant
        fields = ['id', 'user', 'role', 'joined_at', 'is_muted', 'is_video_off']
        read_only_fields = ['joined_at']

class CallRoomSerializer(serializers.ModelSerializer):
    host = UserSerializer(read_only=True)
    participants = CallParticipantSerializer(many=True, read_only=True, source='room_participants')
    active_participants_count = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    
    class Meta:
        model = CallRoom
        fields = [
            'id', 'room_name', 'host', 'room_type', 'is_active',
            'max_participants', 'created_at', 'ended_at',
            'participants', 'active_participants_count', 'is_full'
        ]
        read_only_fields = ['id', 'host', 'created_at', 'ended_at', 'participants']
    
    def get_active_participants_count(self, obj):
        return obj.room_participants.filter(has_left=False).count()
    
    def get_is_full(self, obj):
        return obj.is_full()

class CreateRoomSerializer(serializers.Serializer):
    room_name = serializers.CharField(max_length=200, required=False)
    room_type = serializers.ChoiceField(
        choices=CallRoom.ROOM_TYPES,
        default='video'
    )
    max_participants = serializers.IntegerField(min_value=2, max_value=50, default=10)

class JoinRoomSerializer(serializers.Serializer):
    room_id = serializers.UUIDField(required=True)

class ZegoTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    app_id = serializers.IntegerField(read_only=True)
    room_id = serializers.UUIDField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)

class CallHistorySerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    initiator = UserSerializer(read_only=True)
    
    class Meta:
        model = CallHistory
        fields = [
            'id', 'room', 'participants', 'initiator', 'call_type',
            'status', 'started_at', 'ended_at', 'duration'
        ]
