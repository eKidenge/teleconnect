from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import WebRTCCall, CallSignal, PeerConnection
from .serializers import (
    WebRTCCallSerializer, CallSignalSerializer, PeerConnectionSerializer,
    CreateOfferSerializer, CreateAnswerSerializer, ICECandidateSerializer,
    CallStatusUpdateSerializer
)
# from sessions.models import Session  # Commented out - no sessions app
from django.contrib.auth.models import User

class WebRTCCallViewSet(viewsets.ModelViewSet):
    queryset = WebRTCCall.objects.all()
    serializer_class = WebRTCCallSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Return calls where user is either client or professional
        return WebRTCCall.objects.filter(
            models.Q(session__client=user) | 
            models.Q(session__professional=user)
        ).distinct()
    
    @action(detail=False, methods=['post'])
    def initiate_call(self, request):
        """Client initiates a call"""
        session_id = request.data.get('session_id')
        call_type = request.data.get('call_type', 'audio')
        
        session = get_object_or_404(Session, id=session_id, client=request.user)
        
        # Create WebRTC call
        call = WebRTCCall.objects.create(
            session=session,
            call_type=call_type,
            status='pending',
            room_id=f"room_{session.id}_{int(time.time())}"
        )
        
        # Send notification to professional via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{session.professional.id}",
            {
                'type': 'call_notification',
                'call_id': call.id,
                'session_id': session.id,
                'client_name': session.client.get_full_name(),
                'call_type': call_type
            }
        )
        
        return Response(WebRTCCallSerializer(call).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def accept_call(self, request, pk=None):
        """Professional accepts a call"""
        call = self.get_object()
        user = request.user
        
        if call.session.professional != user:
            return Response({'error': 'Only professional can accept calls'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        call.status = 'ringing'
        call.save()
        
        # Notify client via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{call.session.client.id}",
            {
                'type': 'call_accepted',
                'call_id': call.id,
                'professional_name': user.get_full_name()
            }
        )
        
        return Response({'status': 'call_accepted'})
    
    @action(detail=True, methods=['post'])
    def decline_call(self, request, pk=None):
        """Professional declines a call"""
        call = self.get_object()
        user = request.user
        reason = request.data.get('reason', 'Professional unavailable')
        
        if call.session.professional != user:
            return Response({'error': 'Only professional can decline calls'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        call.status = 'declined'
        call.save()
        
        # Notify client
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{call.session.client.id}",
            {
                'type': 'call_declined',
                'call_id': call.id,
                'reason': reason
            }
        )
        
        return Response({'status': 'call_declined'})
    
    @action(detail=True, methods=['post'])
    def end_call(self, request, pk=None):
        """Either party ends the call"""
        call = self.get_object()
        user = request.user
        
        if user not in [call.session.client, call.session.professional]:
            return Response({'error': 'Not authorized to end this call'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        call.status = 'ended'
        call.ended_at = timezone.now()
        if call.started_at:
            call.duration = int((call.ended_at - call.started_at).total_seconds())
        call.save()
        
        # Notify other party
        other_user = call.session.client if user == call.session.professional else call.session.professional
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{other_user.id}",
            {
                'type': 'call_ended',
                'call_id': call.id,
                'ended_by': user.id
            }
        )
        
        return Response({'status': 'call_ended', 'duration': call.duration})
    
    @action(detail=False, methods=['post'])
    def send_offer(self, request):
        """Send WebRTC offer"""
        serializer = CreateOfferSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            offer = serializer.validated_data['offer']
            user_id = serializer.validated_data['user_id']
            
            session = get_object_or_404(Session, id=session_id)
            user = get_object_or_404(User, id=user_id)
            
            # Store the offer
            call, created = WebRTCCall.objects.get_or_create(
                session=session,
                defaults={
                    'call_type': 'audio',
                    'status': 'connecting',
                    'room_id': f"room_{session.id}"
                }
            )
            
            # Send to other user via WebSocket
            other_user = session.client if user == session.professional else session.professional
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{other_user.id}",
                {
                    'type': 'webrtc_offer',
                    'offer': offer,
                    'from_user': user_id,
                    'session_id': session_id,
                    'call_id': call.id
                }
            )
            
            return Response({'status': 'offer_sent', 'call_id': call.id})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send_answer(self, request):
        """Send WebRTC answer"""
        serializer = CreateAnswerSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            answer = serializer.validated_data['answer']
            user_id = serializer.validated_data['user_id']
            
            session = get_object_or_404(Session, id=session_id)
            user = get_object_or_404(User, id=user_id)
            
            # Send to other user via WebSocket
            other_user = session.client if user == session.professional else session.professional
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{other_user.id}",
                {
                    'type': 'webrtc_answer',
                    'answer': answer,
                    'from_user': user_id,
                    'session_id': session_id
                }
            )
            
            return Response({'status': 'answer_sent'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send_ice_candidate(self, request):
        """Send ICE candidate"""
        serializer = ICECandidateSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            candidate = serializer.validated_data['candidate']
            user_id = serializer.validated_data['user_id']
            
            session = get_object_or_404(Session, id=session_id)
            user = get_object_or_404(User, id=user_id)
            
            # Send to other user via WebSocket
            other_user = session.client if user == session.professional else session.professional
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{other_user.id}",
                {
                    'type': 'webrtc_ice_candidate',
                    'candidate': candidate,
                    'from_user': user_id,
                    'session_id': session_id
                }
            )
            
            return Response({'status': 'candidate_sent'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def update_call_status(self, request):
        """Update call status"""
        serializer = CallStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            status = serializer.validated_data['status']
            user_id = serializer.validated_data['user_id']
            
            session = get_object_or_404(Session, id=session_id)
            user = get_object_or_404(User, id=user_id)
            
            # Update call status
            call = get_object_or_404(WebRTCCall, session=session)
            call.status = status
            if status == 'active' and not call.started_at:
                call.started_at = timezone.now()
            call.save()
            
            # Notify other user
            other_user = session.client if user == session.professional else session.professional
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{other_user.id}",
                {
                    'type': 'call_status_update',
                    'status': status,
                    'from_user': user_id,
                    'session_id': session_id,
                    'call_id': call.id
                }
            )
            
            return Response({'status': 'status_updated'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def get_ice_servers(self, request):
        """Get STUN/TURN server configuration"""
        from django.conf import settings
        return Response(settings.WEBRTC_CONFIG)

class CallSignalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CallSignal.objects.all()
    serializer_class = CallSignalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        call_id = self.request.query_params.get('call_id')
        if call_id:
            return CallSignal.objects.filter(call_id=call_id)
        return CallSignal.objects.none()

class PeerConnectionViewSet(viewsets.ModelViewSet):
    queryset = PeerConnection.objects.all()
    serializer_class = PeerConnectionSerializer
    permission_classes = [IsAuthenticated]

# webrtc/views.py
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])  # you can restrict if needed
def webrtc_config(request):
    return Response({
        "iceServers": settings.WEBRTC_CONFIG.get('iceServers', []),
        "iceTransportPolicy": settings.WEBRTC_CONFIG.get('iceTransportPolicy', 'all'),
    })

