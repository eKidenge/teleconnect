from rest_framework import serializers
from .models import CallSession, CallLog, ChatThread, Message, TypingIndicator, CommunicationSession
from django.contrib.auth import get_user_model
User = get_user_model()

# ========== SHARED ==========
class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'profile_image']

# ========== CALLS ==========
class CallSessionSerializer(serializers.ModelSerializer):
    caller_details = UserMinimalSerializer(source='caller', read_only=True)
    receiver_details = UserMinimalSerializer(source='receiver', read_only=True)
    call_cost = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = CallSession
        fields = [
            'id', 'caller', 'receiver', 'caller_details', 'receiver_details',
            'call_type', 'status', 'channel_name', 'agora_channel', 'agora_token',
            'initiated_at', 'answered_at', 'ended_at', 'duration', 'duration_formatted',
            'session_id', 'call_rate', 'call_cost'
        ]
        read_only_fields = ['id', 'initiated_at', 'answered_at', 'ended_at', 'duration', 
                          'call_cost', 'agora_token', 'channel_name']
    
    def get_call_cost(self, obj):
        return obj.call_cost
    
    def get_duration_formatted(self, obj):
        if not obj.duration:
            return "00:00"
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f"{minutes:02d}:{seconds:02d}"


class CallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLog
        fields = ['id', 'call_session', 'event_type', 'timestamp', 'metadata']


class CallInitiateSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField(required=True)
    call_type = serializers.ChoiceField(choices=['voice', 'video'], default='voice')
    session_id = serializers.CharField(required=False)


class AgoraTokenSerializer(serializers.Serializer):
    channel_name = serializers.CharField(required=True)
    uid = serializers.IntegerField(required=True)
    role = serializers.ChoiceField(choices=['publisher', 'subscriber'], default='publisher')

# ========== CHAT ==========
class MessageSerializer(serializers.ModelSerializer):
    sender_details = UserMinimalSerializer(source='sender', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'thread', 'sender', 'sender_details', 'message_type', 'content',
            'file', 'file_url', 'file_name', 'file_size', 'is_read', 
            'read_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'sender']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class ChatThreadSerializer(serializers.ModelSerializer):
    user1_details = UserMinimalSerializer(source='user1', read_only=True)
    user2_details = UserMinimalSerializer(source='user2', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_user = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatThread
        fields = [
            'id', 'user1', 'user2', 'user1_details', 'user2_details',
            'created_at', 'updated_at', 'session_id', 'is_active',
            'last_message', 'unread_count', 'other_user'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return MessageSerializer(last_msg, context=self.context).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0
    
    def get_other_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            other = obj.other_user(request.user)
            return UserMinimalSerializer(other).data
        return None


class TypingIndicatorSerializer(serializers.ModelSerializer):
    user_details = UserMinimalSerializer(source='user', read_only=True)
    
    class Meta:
        model = TypingIndicator
        fields = ['id', 'thread', 'user', 'user_details', 'is_typing', 'last_typing']


class CommunicationSessionSerializer(serializers.ModelSerializer):
    client_details = UserMinimalSerializer(source='client', read_only=True)
    professional_details = UserMinimalSerializer(source='professional', read_only=True)
    
    class Meta:
        model = CommunicationSession
        fields = [
            'id', 'thread', 'call_session', 'session_id', 'client', 'professional',
            'client_details', 'professional_details', 'category', 'subcategory',
            'communication_type', 'status', 'started_at', 'ended_at', 
            'payment_status', 'amount', 'duration'
        ]
