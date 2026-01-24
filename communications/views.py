from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
import json
import time

from .models import CallSession, CallLog, ChatThread, Message, TypingIndicator
from .serializers import (
    CallSessionSerializer, CallInitiateSerializer, AgoraTokenSerializer,
    ChatThreadSerializer, MessageSerializer, TypingIndicatorSerializer
)
from .agora import agora_token_generator, AgoraChannelManager

# ========== CALL VIEWS ==========
class CallSessionViewSet(viewsets.ModelViewSet):
    queryset = CallSession.objects.all()
    serializer_class = CallSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return CallSession.objects.filter(
            Q(caller=user) | Q(receiver=user)
        ).order_by('-initiated_at')
    
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        serializer = CallInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        receiver_id = serializer.validated_data['receiver_id']
        call_type = serializer.validated_data['call_type']
        
        # Generate unique channel and token
        channel_name = AgoraChannelManager.generate_channel_name(
            request.user.id, 
            receiver_id
        )
        
        agora_token = agora_token_generator.generate_rtc_token(
            channel_name=channel_name,
            uid=request.user.id,
            role='publisher'
        )
        
        # Create call session
        call_session = CallSession.objects.create(
            caller=request.user,
            receiver_id=receiver_id,
            call_type=call_type,
            channel_name=channel_name,
            agora_channel=channel_name,
            agora_token=agora_token,
            call_rate=1.2,  # Default rate
        )
        
        CallLog.objects.create(
            call_session=call_session,
            event_type='initiated',
            metadata={'call_type': call_type}
        )
        
        return Response(
            CallSessionSerializer(call_session, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        call_session = self.get_object()
        
        if call_session.receiver != request.user:
            return Response(
                {"error": "Only receiver can accept call"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate token for receiver
        agora_token = agora_token_generator.generate_rtc_token(
            channel_name=call_session.channel_name,
            uid=request.user.id,
            role='publisher'
        )
        
        call_session.status = 'ongoing'
        call_session.answered_at = timezone.now()
        call_session.save()
        
        CallLog.objects.create(call_session=call_session, event_type='accepted')
        
        return Response({
            'status': 'accepted',
            'agora_token': agora_token,
            'channel_name': call_session.channel_name,
            'call_session_id': str(call_session.id)
        })
    
    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        call_session = self.get_object()
        
        if request.user not in [call_session.caller, call_session.receiver]:
            return Response(
                {"error": "Not a participant in this call"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Calculate duration
        if call_session.answered_at:
            duration = (timezone.now() - call_session.answered_at).seconds
        else:
            duration = 0
        
        call_session.status = 'completed'
        call_session.ended_at = timezone.now()
        call_session.duration = duration
        call_session.save()
        
        CallLog.objects.create(
            call_session=call_session,
            event_type='ended',
            metadata={'duration': duration}
        )
        
        return Response({
            'status': 'ended',
            'duration': duration,
            'call_cost': call_session.call_cost
        })
    
    @action(detail=False, methods=['post'])
    def generate_token(self, request):
        serializer = AgoraTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        channel_name = serializer.validated_data['channel_name']
        uid = serializer.validated_data['uid']
        role = serializer.validated_data['role']
        
        # Verify channel access
        user1_id, user2_id = AgoraChannelManager.parse_channel_name(channel_name)
        if not user1_id or request.user.id not in [user1_id, user2_id]:
            return Response(
                {"error": "Unauthorized access to channel"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        token = agora_token_generator.generate_rtc_token(
            channel_name=channel_name,
            uid=uid,
            role=role
        )
        
        return Response({
            'token': token,
            'channel_name': channel_name,
            'uid': uid
        })
    
    @action(detail=False, methods=['get'])
    def active_calls(self, request):
        active_calls = CallSession.objects.filter(
            Q(caller=request.user) | Q(receiver=request.user),
            status__in=['initiated', 'ringing', 'ongoing']
        )
        serializer = self.get_serializer(active_calls, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def call_history(self, request):
        history = CallSession.objects.filter(
            Q(caller=request.user) | Q(receiver=request.user),
            status='completed'
        ).order_by('-ended_at')[:50]
        serializer = self.get_serializer(history, many=True)
        return Response(serializer.data)

# ========== CHAT VIEWS ==========
class ChatThreadViewSet(viewsets.ModelViewSet):
    queryset = ChatThread.objects.all()
    serializer_class = ChatThreadSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return ChatThread.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).order_by('-updated_at')
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        thread = self.get_object()
        
        # Mark unread messages as read
        unread_messages = thread.messages.filter(is_read=False).exclude(sender=request.user)
        unread_messages.update(is_read=True, read_at=timezone.now())
        
        messages = thread.messages.all().order_by('created_at')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        thread = self.get_object()
        
        serializer = MessageSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(thread=thread, sender=request.user)
        thread.save()  # Update timestamp
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def typing(self, request, pk=None):
        thread = self.get_object()
        is_typing = request.data.get('is_typing', False)
        
        indicator, created = TypingIndicator.objects.update_or_create(
            thread=thread,
            user=request.user,
            defaults={'is_typing': is_typing}
        )
        
        serializer = TypingIndicatorSerializer(indicator)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def with_user(self, request):
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find or create thread
        thread = ChatThread.objects.filter(
            (Q(user1=request.user, user2_id=user_id) | 
             Q(user1_id=user_id, user2=request.user))
        ).first()
        
        if not thread:
            thread = ChatThread.objects.create(
                user1=request.user,
                user2_id=user_id
            )
        
        serializer = self.get_serializer(thread)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            Q(thread__user1=user) | Q(thread__user2=user)
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
