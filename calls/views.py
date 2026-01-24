from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import models
import uuid
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CallRoom, CallParticipant, CallHistory
from .serializers import (
    CallRoomSerializer, CreateRoomSerializer, JoinRoomSerializer,
    CallParticipantSerializer, CallHistorySerializer
)
from .services import CallManager, ZegoService
from .permissions import IsRoomParticipant, IsRoomHost

# =====================
# TOKEN AUTHENTICATION DECORATORS (Same as QuickConnect)
# =====================

def get_authenticated_user(request):
    """Get authenticated user using QuickConnect's token authentication"""
    # Check for Token authentication (like QuickConnect)
    auth_header = request.headers.get('Authorization')
    
    if auth_header and auth_header.startswith('Token '):
        token_key = auth_header.split(' ')[1]
        try:
            from django.contrib.auth.models import User
            from rest_framework.authtoken.models import Token
            token = Token.objects.get(key=token_key)
            return token.user
        except:
            return None
    # Fallback to Django session auth
    elif request.user.is_authenticated:
        return request.user
    else:
        return None

# =====================
# CALL ROOM VIEWS (Updated for QuickConnect Auth)
# =====================

class CallRoomViewSet(viewsets.ModelViewSet):
    """Manage call rooms - Uses QuickConnect TokenAuthentication"""
    serializer_class = CallRoomSerializer
    
    # Use EXACTLY the same authentication as QuickConnect
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Users can see rooms they're participating in
        user = self.request.user
        return CallRoom.objects.filter(
            room_participants__user=user,
            room_participants__has_left=False,
            is_active=True
        ).distinct()
    
    def create(self, request):
        """Create a new call room"""
        serializer = CreateRoomSerializer(data=request.data)
        if serializer.is_valid():
            try:
                room = CallManager.create_room(
                    user=request.user,
                    room_name=serializer.validated_data.get('room_name'),
                    room_type=serializer.validated_data.get('room_type', 'video'),
                    max_participants=serializer.validated_data.get('max_participants', 10)
                )
                
                # Generate ZEGO token for host
                zego_token = ZegoService.generate_token(
                    user_id=str(request.user.id),
                    room_id=str(room.id)
                )
                
                return Response({
                    'success': True,
                    'room': CallRoomSerializer(room, context={'request': request}).data,
                    'zego_token': zego_token,
                    'message': 'Room created successfully'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join an existing call room"""
        try:
            result = CallManager.join_room(request.user, pk)
            
            return Response({
                'success': True,
                'room': CallRoomSerializer(result['room'], context={'request': request}).data,
                'zego_token': result['zego_token'],
                'is_new_joiner': result['is_new_joiner'],
                'message': 'Joined room successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave a call room"""
        try:
            success = CallManager.leave_room(request.user, pk)
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Left room successfully'
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Not in room or already left'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        """Get all active participants in a room"""
        try:
            participants = CallManager.get_room_participants(pk)
            serializer = CallParticipantSerializer(participants, many=True)
            return Response({
                'success': True,
                'participants': serializer.data,
                'count': len(participants)
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsRoomHost])
    def end_call(self, request, pk=None):
        """Host ends the call for everyone"""
        try:
            room = self.get_object()
            room.end_call()
            
            # Create call history
            CallHistory.objects.create(
                room=room,
                initiator=room.host,
                call_type=f"{room.room_type}_call",
                started_at=room.created_at,
                ended_at=timezone.now()
            )
            
            return Response({
                'success': True,
                'message': 'Call ended successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =====================
# CALL HISTORY VIEWS
# =====================

class CallHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """View call history"""
    serializer_class = CallHistorySerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CallHistory.objects.filter(
            participants=self.request.user
        ).order_by('-started_at')

# =====================
# ZEGO TOKEN VIEWS (Updated for QuickConnect Auth)
# =====================

class ZegoTokenView(APIView):
    """Get ZEGO token for RTC - Uses QuickConnect TokenAuthentication"""
    
    # Use EXACTLY the same authentication as QuickConnect
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            data = request.data
            
            # Extract room_id and user_id from request
            room_id = data.get('room_id')
            user_id = data.get('user_id', str(request.user.id))
            
            if not room_id:
                return Response({
                    'success': False,
                    'error': 'room_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"🔐 Generating token for authenticated user: {request.user.id} ({request.user.username}), room: {room_id}")
            
            # Generate token using the authenticated user
            token_data = ZegoService.generate_token(
                user_id=user_id,
                room_id=room_id
            )
            
            return Response({
                'success': True,
                **token_data,
                'message': 'Token generated successfully'
            })
            
        except Exception as e:
            print(f"❌ Token generation error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =====================
# PUBLIC ZEGO TOKEN VIEW (For Testing)
# =====================

@csrf_exempt
@require_http_methods(["POST"])
def zego_token_public(request):
    """Public endpoint to get ZEGO token (for testing only) - NO authentication required"""
    try:
        data = json.loads(request.body)
        
        room_id = data.get('room_id', 'test_room')
        user_id = data.get('user_id', 'test_user')
        
        if not room_id:
            return JsonResponse({
                'success': False,
                'error': 'room_id is required'
            }, status=400)
        
        print(f"🔐 Generating PUBLIC token for user: {user_id}, room: {room_id}")
        
        # Generate token using ZegoService
        token_data = ZegoService.generate_token(
            user_id=user_id,
            room_id=room_id
        )
        
        return JsonResponse({
            'success': True,
            **token_data,
            'note': 'Public endpoint - for testing only'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        print(f"❌ Public token generation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# =====================
# ACTIVE ROOMS VIEW
# =====================

class ActiveRoomsView(APIView):
    """Get all active rooms user can join"""
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            user = request.user
            
            # Rooms user is not in yet
            user_rooms = CallRoom.objects.filter(
                room_participants__user=user,
                room_participants__has_left=False
            ).values_list('id', flat=True)
            
            # Get available rooms (active, not full, user not already in)
            available_rooms = CallRoom.objects.filter(
                is_active=True
            ).exclude(
                id__in=user_rooms
            ).annotate(
                participant_count=models.Count('room_participants', filter=models.Q(room_participants__has_left=False))
            ).filter(
                participant_count__lt=models.F('max_participants')
            )
            
            serializer = CallRoomSerializer(available_rooms, many=True)
            
            return Response({
                'success': True,
                'rooms': serializer.data,
                'count': available_rooms.count()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =====================
# SIMPLE API VIEWS (For Testing/Health Checks)
# =====================

@csrf_exempt
@require_http_methods(["GET"])
def calls_api_home(request):
    """Calls API landing page"""
    return JsonResponse({
        'message': 'Welcome to TeleConnect Calls API',
        'status': 'Server is running',
        'endpoints': {
            'create_room': '/api/calls/rooms/',
            'join_room': '/api/calls/rooms/{id}/join/',
            'leave_room': '/api/calls/rooms/{id}/leave/',
            'room_participants': '/api/calls/rooms/{id}/participants/',
            'end_call': '/api/calls/rooms/{id}/end_call/',
            'get_token': '/api/calls/token/',
            'get_token_public': '/api/calls/token/public/',
            'active_rooms': '/api/calls/active-rooms/',
            'call_history': '/api/calls/history/',
        },
        'authentication': 'Token Authentication (Header: Authorization: Token <token>)'
    })

# =====================
# TEST AUTHENTICATION VIEW
# =====================

@csrf_exempt
@require_http_methods(["GET"])
def test_auth(request):
    """Test if authentication is working"""
    user = get_authenticated_user(request)
    
    if user:
        return JsonResponse({
            'success': True,
            'authenticated': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            },
            'message': 'Authentication successful'
        })
    else:
        return JsonResponse({
            'success': False,
            'authenticated': False,
            'message': 'Authentication failed. Provide Authorization: Token <token> header'
        }, status=401)

# =====================
# USER CALL STATS VIEW
# =====================

@csrf_exempt
@require_http_methods(["GET"])
def user_call_stats(request):
    """Get user call statistics"""
    try:
        user = get_authenticated_user(request)
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        # Get user's call statistics
        total_calls = CallHistory.objects.filter(participants=user).count()
        completed_calls = CallHistory.objects.filter(participants=user, status='completed').count()
        total_duration = CallHistory.objects.filter(
            participants=user, 
            duration__isnull=False
        ).aggregate(total_duration=models.Sum('duration'))
        
        # Recent calls
        recent_calls = CallHistory.objects.filter(participants=user).order_by('-started_at')[:5]
        recent_calls_data = []
        for call in recent_calls:
            recent_calls_data.append({
                'id': str(call.id),
                'call_type': call.call_type,
                'status': call.status,
                'started_at': call.started_at.isoformat() if call.started_at else None,
                'duration': call.duration.total_seconds() if call.duration else 0,
                'participant_count': call.participants.count()
            })
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_calls': total_calls,
                'completed_calls': completed_calls,
                'completion_rate': round((completed_calls / total_calls * 100) if total_calls > 0 else 0, 2),
                'total_duration_minutes': round((total_duration['total_duration'].total_seconds() / 60) if total_duration['total_duration'] else 0, 2)
            },
            'recent_calls': recent_calls_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# =====================
# ROOM INFO VIEW
# =====================

@csrf_exempt
@require_http_methods(["GET"])
def room_info(request, room_id):
    """Get detailed information about a call room"""
    try:
        user = get_authenticated_user(request)
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        room = get_object_or_404(CallRoom, id=room_id)
        
        # Check if user is a participant
        is_participant = CallParticipant.objects.filter(
            room=room,
            user=user,
            has_left=False
        ).exists()
        
        if not is_participant and not user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Not authorized to view this room'
            }, status=403)
        
        # Get room participants
        participants = CallParticipant.objects.filter(
            room=room,
            has_left=False
        ).select_related('user')
        
        participants_data = []
        for participant in participants:
            participants_data.append({
                'id': participant.user.id,
                'username': participant.user.username,
                'role': participant.role,
                'joined_at': participant.joined_at.isoformat(),
                'is_muted': participant.is_muted,
                'is_video_off': participant.is_video_off
            })
        
        # Get room details
        room_data = {
            'id': str(room.id),
            'room_name': room.room_name,
            'room_type': room.room_type,
            'host': {
                'id': room.host.id,
                'username': room.host.username
            },
            'is_active': room.is_active,
            'max_participants': room.max_participants,
            'created_at': room.created_at.isoformat(),
            'ended_at': room.ended_at.isoformat() if room.ended_at else None,
            'participant_count': len(participants_data),
            'is_full': len(participants_data) >= room.max_participants
        }
        
        return JsonResponse({
            'success': True,
            'room': room_data,
            'participants': participants_data,
            'is_participant': is_participant
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# =====================
# CREATE ROOM SIMPLE (Alternative to DRF viewset)
# =====================

@csrf_exempt
@require_http_methods(["POST"])
def create_room_simple(request):
    """Simple endpoint to create a call room"""
    try:
        user = get_authenticated_user(request)
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        data = json.loads(request.body)
        
        room_name = data.get('room_name', f"{user.username}'s Room")
        room_type = data.get('room_type', 'video')
        max_participants = data.get('max_participants', 10)
        
        # Create room
        room = CallManager.create_room(
            user=user,
            room_name=room_name,
            room_type=room_type,
            max_participants=max_participants
        )
        
        # Generate ZEGO token for host
        zego_token = ZegoService.generate_token(
            user_id=str(user.id),
            room_id=str(room.id)
        )
        
        return JsonResponse({
            'success': True,
            'room': {
                'id': str(room.id),
                'room_name': room.room_name,
                'room_type': room.room_type,
                'host_id': user.id,
                'max_participants': room.max_participants,
                'created_at': room.created_at.isoformat()
            },
            'zego_token': zego_token,
            'message': 'Room created successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
