import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Professional, Session
# Add these imports at the top if not already there ON 8TH DEC 2025 AT 9:42PM
import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from rest_framework.authtoken.models import Token
from .models import Professional, Session, User
from django.utils import timezone


class QuickConnectConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_id = None

    async def connect(self):
        await self.accept()
        print("✅ WebSocket connected - QuickConnect")
        
        # Immediately send ALL professionals without any filtering
        try:
            professionals = await self.get_all_professionals()
            if not professionals:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "No professionals found in database."
                }))
            else:
                # Send as raw array to match frontend expectation
                await self.send(text_data=json.dumps(professionals))
                print(f"📨 Sent {len(professionals)} professionals to client")
        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error", 
                "message": f"Server error: {str(e)}"
            }))

    async def disconnect(self, close_code):
        print(f"🔌 WebSocket disconnected - QuickConnect: {close_code}")
        if self.client_id:
            await self.release_professional_by_client(self.client_id)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            self.client_id = data.get("client_id")

            print(f"📨 Received: {message_type} from {self.client_id}")

            if message_type == "lock":
                await self.handle_lock_professional(data)
                
            elif message_type == "release":
                await self.handle_release_professional(data)
                
            elif message_type == "get_available_professionals":
                # Always return ALL professionals
                professionals = await self.get_all_professionals()
                await self.send(text_data=json.dumps(professionals))
                
            elif message_type == "client_identification":
                await self.send(text_data=json.dumps({
                    "type": "client_identified",
                    "client_id": self.client_id
                }))
                
            else:
                # Default: send all professionals
                professionals = await self.get_all_professionals()
                await self.send(text_data=json.dumps(professionals))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Invalid JSON format"
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Server error: {str(e)}"
            }))

    async def handle_lock_professional(self, data):
        """Handle professional locking"""
        pro_id = data.get("professional_id")
        client_id = data.get("client_id")
        
        professional = await self.lock_professional(pro_id, client_id)
        if professional:
            await self.send(text_data=json.dumps({
                "type": "locked",
                "professional": professional
            }))
            print(f"🔒 Locked professional: {professional['name']}")
        else:
            await self.send(text_data=json.dumps({
                "type": "error", 
                "message": "Professional is not available or already locked."
            }))

    async def handle_release_professional(self, data):
        """Handle professional release"""
        pro_id = data.get("professional_id")
        client_id = data.get("client_id")
        
        await self.release_professional(pro_id, client_id)
        # Send updated list after release
        professionals = await self.get_all_professionals()
        await self.send(text_data=json.dumps(professionals))

    @sync_to_async
    def get_all_professionals(self):
        """Get ALL professionals from database with consistent status"""
        try:
            # Get ALL professionals without any filtering
            professionals = Professional.objects.all().values(
                "id", "name", "specialization", "rate", "available", 
                "average_rating", "total_sessions", "status", "locked_by"
            )
            
            professional_list = []
            for pro in professionals:
                # Ensure consistency: if locked_by exists, available should be False
                is_locked = pro["locked_by"] is not None and pro["locked_by"] != ""
                is_available = pro["available"] and not is_locked
                
                professional_list.append({
                    "id": str(pro["id"]),
                    "name": pro["name"], 
                    "specialization": pro["specialization"],
                    "rate": float(pro["rate"]),
                    "available": is_available,  # Override with consistent value
                    "lockedBy": pro["locked_by"],
                    "experience": pro.get("total_sessions", 0),
                    "rating": float(pro.get("average_rating", 0.0)),
                    "status": pro.get("status", "unknown")
                })
            
            print(f"🔍 Found {len(professional_list)} total professionals in database")
            
            # Debug: Print each professional with ALL details
            print("🔍 All professionals with details:")
            for pro in professional_list:
                print(f"   👨‍💼 {pro['name']} - {pro['specialization']} - KSH {pro['rate']}/min - Status: {pro['status']} - Available: {pro['available']} - Locked: {pro['lockedBy']}")
            
            return professional_list
            
        except Exception as e:
            print(f"❌ Error getting professionals: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    @sync_to_async
    def lock_professional(self, pro_id, client_id):
        """Lock a professional for a client - with validation"""
        try:
            pro = Professional.objects.get(id=pro_id)
            
            # Check if professional is already locked by someone else
            if pro.locked_by and pro.locked_by != client_id:
                print(f"❌ Professional {pro_id} already locked by: {pro.locked_by}")
                return None
                
            # Update the professional
            pro.locked_by = client_id
            pro.available = False
            pro.save()
            
            print(f"🔒 Successfully locked {pro.name} for client {client_id}")
            
            return {
                "id": str(pro.id),
                "name": pro.name,
                "specialization": pro.specialization,
                "rate": float(pro.rate),
                "available": False,
                "lockedBy": client_id,
                "experience": pro.total_sessions,
                "rating": float(pro.average_rating)
            }
                
        except Professional.DoesNotExist:
            print(f"❌ Professional {pro_id} not found")
            return None
        except Exception as e:
            print(f"❌ Error locking professional: {str(e)}")
            return None

    @sync_to_async
    def release_professional(self, pro_id, client_id):
        """Release a professional"""
        try:
            pro = Professional.objects.get(id=pro_id)
            # Only release if locked by this client
            if pro.locked_by == client_id:
                pro.locked_by = None
                pro.available = True
                pro.save()
                print(f"🔓 Released professional: {pro.name}")
            else:
                print(f"⚠️  Professional {pro.name} not locked by client {client_id}")
        except Professional.DoesNotExist:
            print(f"❌ Professional {pro_id} not found for release")
        except Exception as e:
            print(f"❌ Error releasing professional: {str(e)}")

    @sync_to_async
    def release_professional_by_client(self, client_id):
        """Release all professionals locked by a client"""
        if client_id:
            try:
                # Clean up any invalid lock values
                professionals_to_release = Professional.objects.filter(
                    locked_by=client_id
                )
                
                released_count = 0
                for pro in professionals_to_release:
                    pro.locked_by = None
                    pro.available = True
                    pro.save()
                    released_count += 1
                    print(f"🔓 Released professional: {pro.name}")
                
                print(f"🔓 Released {released_count} professionals for client: {client_id}")
                
                # Also clean up any professionals with invalid lock values
                invalid_locked = Professional.objects.filter(
                    locked_by="PROFESSION"
                )
                for pro in invalid_locked:
                    pro.locked_by = None
                    pro.available = True
                    pro.save()
                    print(f"🔓 Cleaned invalid lock for: {pro.name}")
                    
            except Exception as e:
                print(f"❌ Error releasing professionals by client: {str(e)}")


class SessionConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.professional_id = None
        self.client_id = None
        self.session_group_name = None

    async def connect(self):
        try:
            self.professional_id = self.scope['url_route']['kwargs']['professional_id']
            self.client_id = self.scope['url_route']['kwargs']['client_id']
            self.session_group_name = f'session_{self.professional_id}_{self.client_id}'
            
            # Join session group
            await self.channel_layer.group_add(
                self.session_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Create session record
            await self.create_session()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'session_connected',
                'message': 'Session started successfully',
                'session_id': f'{self.professional_id}_{self.client_id}',
                'professional_id': self.professional_id,
                'client_id': self.client_id
            }))
            
            print(f"✅ Session started: {self.session_group_name}")
            
        except Exception as e:
            print(f"❌ Session connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            # Leave session group
            if self.session_group_name:
                await self.channel_layer.group_discard(
                    self.session_group_name,
                    self.channel_name
                )
            
            # End session
            await self.end_session()
            print(f"🔌 Session ended: {self.session_group_name}, code: {close_code}")
            
        except Exception as e:
            print(f"❌ Session disconnect error: {str(e)}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            print(f"📨 Session received {message_type} from {self.client_id}")
            
            # Route message to appropriate handler
            handlers = {
                'chat_message': self.handle_chat_message,
                'call_initiate': self.handle_call_initiation,
                'call_end': self.handle_call_end,
                'video_initiate': self.handle_video_initiation,
                'video_end': self.handle_video_end,
                'end_session': self.handle_session_end,
                'client_paused': self.handle_client_paused,
                'confirm_session': self.handle_confirm_session,
            }
            
            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                print(f"❓ Unknown session message type: {message_type}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in session: {text_data}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid message format'
            }))
        except Exception as e:
            print(f"❌ Session receive error: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Server error: {str(e)}'
            }))

    async def handle_confirm_session(self, data):
        """Handle session confirmation from client"""
        mode = data.get('mode', 'chat')
        timestamp = data.get('timestamp')
        
        # Update session type
        await self.update_session_type(mode)
        
        # Notify professional about session confirmation
        await self.channel_layer.group_send(
            f'professional_{self.professional_id}',
            {
                'type': 'session_confirmed',
                'client_id': self.client_id,
                'mode': mode,
                'timestamp': timestamp,
                'professional_id': self.professional_id
            }
        )
        
        await self.send(text_data=json.dumps({
            'type': 'session_confirmed',
            'mode': mode,
            'timestamp': timestamp
        }))

    async def handle_chat_message(self, data):
        """Handle chat messages from client to professional"""
        message_text = data.get('text', '').strip()
        if not message_text:
            return
            
        message_id = data.get('message_id', str(uuid.uuid4()))
        timestamp = data.get('timestamp')
        
        # Save message to database
        await self.save_chat_message(message_text, message_id, timestamp)
        
        # Notify professional about new message
        await self.channel_layer.group_send(
            f'professional_{self.professional_id}',
            {
                'type': 'professional_chat_message',
                'message': message_text,
                'client_id': self.client_id,
                'message_id': message_id,
                'timestamp': timestamp,
                'professional_id': self.professional_id
            }
        )
        
        # Send confirmation to client
        await self.send(text_data=json.dumps({
            'type': 'message_sent',
            'message_id': message_id,
            'timestamp': timestamp
        }))

    async def handle_call_initiation(self, data):
        """Handle call initiation"""
        call_type = data.get('call_type', 'audio')
        timestamp = data.get('timestamp')
        
        # Update session type
        await self.update_session_type(call_type)
        
        # Notify professional about incoming call
        await self.channel_layer.group_send(
            f'professional_{self.professional_id}',
            {
                'type': 'incoming_call',
                'client_id': self.client_id,
                'call_type': call_type,
                'timestamp': timestamp,
                'professional_id': self.professional_id
            }
        )
        
        await self.send(text_data=json.dumps({
            'type': 'call_initiated',
            'call_type': call_type,
            'timestamp': timestamp
        }))

    async def handle_video_initiation(self, data):
        """Handle video call initiation"""
        await self.handle_call_initiation(data)  # Same logic as call initiation

    async def handle_call_end(self, data):
        """Handle call/video ending"""
        call_type = data.get('call_type', 'audio')
        duration = data.get('duration', 0)
        cost = data.get('cost', 0)
        
        # Notify professional about call end
        await self.channel_layer.group_send(
            f'professional_{self.professional_id}',
            {
                'type': 'call_ended',
                'client_id': self.client_id,
                'call_type': call_type,
                'duration': duration,
                'cost': cost,
                'professional_id': self.professional_id
            }
        )
        
        await self.send(text_data=json.dumps({
            'type': 'call_ended_confirm',
            'call_type': call_type,
            'duration': duration,
            'cost': cost
        }))

    async def handle_video_end(self, data):
        """Handle video call ending"""
        await self.handle_call_end(data)  # Same logic as call end

    async def handle_session_end(self, data):
        """Handle session ending by client"""
        final_cost = data.get('final_cost', 0)
        final_duration = data.get('final_duration', 0)
        
        # Update session with final details
        await self.update_session(final_duration, final_cost)
        
        # Notify professional about session end
        await self.channel_layer.group_send(
            f'professional_{self.professional_id}',
            {
                'type': 'session_ended',
                'client_id': self.client_id,
                'final_cost': final_cost,
                'final_duration': final_duration,
                'professional_id': self.professional_id
            }
        )
        
        await self.send(text_data=json.dumps({
            'type': 'session_ended_confirm',
            'final_cost': final_cost,
            'final_duration': final_duration
        }))

    async def handle_client_paused(self, data):
        """Handle client app going to background"""
        await self.channel_layer.group_send(
            f'professional_{self.professional_id}',
            {
                'type': 'client_paused',
                'client_id': self.client_id,
                'professional_id': self.professional_id,
                'timestamp': data.get('timestamp')
            }
        )

    # Professional message handlers
    async def professional_chat_message(self, event):
        """Receive chat message from professional"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'text': event['message'],
            'message_id': event.get('message_id'),
            'timestamp': event.get('timestamp'),
            'sender': 'professional'
        }))

    async def call_accepted(self, event):
        """Professional accepted the call"""
        await self.send(text_data=json.dumps({
            'type': 'call_accepted',
            'professional_id': event['professional_id'],
            'timestamp': event.get('timestamp')
        }))

    async def call_rejected(self, event):
        """Professional rejected the call"""
        await self.send(text_data=json.dumps({
            'type': 'call_rejected',
            'professional_id': event['professional_id'],
            'reason': event.get('reason', 'Busy'),
            'timestamp': event.get('timestamp')
        }))

    async def professional_ended_session(self, event):
        """Professional ended the session"""
        await self.send(text_data=json.dumps({
            'type': 'session_ended_by_professional',
            'final_cost': event.get('final_cost'),
            'final_duration': event.get('final_duration'),
            'reason': event.get('reason', 'Session completed')
        }))

    # Database operations
    @sync_to_async
    def create_session(self):
        """Create a new session record"""
        try:
            professional = Professional.objects.get(id=self.professional_id)
            Session.objects.create(
                professional=professional,
                client_id=self.client_id,
                status='active',
                session_type='pending'
            )
            print(f"✅ Session record created for {self.client_id} with {self.professional_id}")
        except Professional.DoesNotExist:
            print(f"❌ Professional {self.professional_id} not found")
        except Exception as e:
            print(f"❌ Session creation error: {str(e)}")

    @sync_to_async
    def update_session_type(self, session_type):
        """Update session type"""
        try:
            session = Session.objects.get(
                professional_id=self.professional_id,
                client_id=self.client_id,
                status='active'
            )
            session.session_type = session_type
            session.save()
            print(f"✅ Session type updated to: {session_type}")
        except Session.DoesNotExist:
            print(f"❌ Active session not found for type update")

    @sync_to_async
    def save_chat_message(self, message_text, message_id, timestamp):
        """Save chat message to database"""
        try:
            # You might want to create a ChatMessage model for this
            # For now, we'll just log it
            print(f"💬 Chat message saved: {message_text} (ID: {message_id})")
        except Exception as e:
            print(f"❌ Error saving chat message: {str(e)}")

    @sync_to_async
    def update_session(self, duration, cost):
        """Update session with final details"""
        try:
            session = Session.objects.get(
                professional_id=self.professional_id,
                client_id=self.client_id,
                status='active'
            )
            session.duration = duration
            session.cost = cost
            session.status = 'completed'
            session.save()
            print(f"✅ Session updated: {duration}min, KSH{cost}")
        except Session.DoesNotExist:
            print(f"❌ Active session not found for update")
        except Exception as e:
            print(f"❌ Error updating session: {str(e)}")

    @sync_to_async
    def end_session(self):
        """End session on disconnect"""
        try:
            session = Session.objects.get(
                professional_id=self.professional_id,
                client_id=self.client_id,
                status='active'
            )
            session.status = 'disconnected'
            session.save()
            print(f"🔌 Session marked as disconnected")
        except Session.DoesNotExist:
            pass  # Session might already be ended
        except Exception as e:
            print(f"❌ Error ending session: {str(e)}")


# consumers.py - Add WebSocket support
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'call_{self.session_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connected successfully'
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'call_joined':
            # Handle user joining call
            await self.handle_call_joined(text_data_json)
        elif message_type == 'call_ended':
            # Handle call ending
            await self.handle_call_ended(text_data_json)
        elif message_type == 'call_quality_update':
            # Handle quality updates
            await self.handle_quality_update(text_data_json)
        elif message_type == 'recording_status':
            # Handle recording status
            await self.handle_recording_status(text_data_json)

    async def handle_call_joined(self, data):
        user_type = data.get('user_type')
        user_id = data.get('user_id')
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_type': user_type,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_call_ended(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_ended',
                'ended_by': data.get('ended_by'),
                'reason': data.get('reason'),
                'duration': data.get('duration'),
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_quality_update(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'quality_update',
                'quality': data.get('quality'),
                'network_quality': data.get('network_quality'),
                'audio_issues': data.get('audio_issues', []),
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_recording_status(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'recording_status',
                'recording': data.get('recording'),
                'consent': data.get('consent'),
                'timestamp': timezone.now().isoformat()
            }
        )

    # Receive message from room group
    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_type': event['user_type'],
            'user_id': event['user_id'],
            'timestamp': event['timestamp']
        }))

    async def call_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'ended_by': event['ended_by'],
            'reason': event['reason'],
            'duration': event['duration'],
            'timestamp': event['timestamp']
        }))

    async def quality_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'quality_update',
            'quality': event['quality'],
            'network_quality': event['network_quality'],
            'audio_issues': event['audio_issues'],
            'timestamp': event['timestamp']
        }))

    async def recording_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'recording_status',
            'recording': event['recording'],
            'consent': event['consent'],
            'timestamp': event['timestamp']
        }))

# ADDED ON 8TH FOR BESOCKET
# ADD THIS NEW CLASS - PROFESSIONAL CALL NOTIFICATIONS WEBSOCKET
class ProfessionalCallNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket for real-time call notifications to professionals
    This matches the frontend trying to connect to: ws://teleconnect-krga.onrender.com/ws/calls/{professional_id}/
    """
    
    async def connect(self):
        try:
            # Get professional_id from URL
            self.professional_id = self.scope['url_route']['kwargs']['professional_id']
            self.room_group_name = f'calls_professional_{self.professional_id}'
            
            print(f"🔌 Attempting WebSocket connection for professional {self.professional_id}")
            
            # Try to get authentication token from query string
            query_params = self.scope.get('query_string', b'').decode('utf-8')
            print(f"📡 Query params: {query_params}")
            
            # Accept connection first (we'll authenticate in receive)
            await self.accept()
            
            # Add to room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Send connection success message
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': f'✅ WebSocket connected for professional {self.professional_id}',
                'professional_id': self.professional_id,
                'timestamp': timezone.now().isoformat(),
                'room': self.room_group_name
            }))
            
            print(f"✅ Professional Call WebSocket connected: {self.room_group_name}")
            
            # Send ping immediately to test connection
            await self.send(text_data=json.dumps({
                'type': 'ping',
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            print(f"❌ WebSocket connection error: {str(e)}")
            try:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Connection error: {str(e)}'
                }))
            except:
                pass
            await self.close()
    
    async def disconnect(self, close_code):
        print(f"🔌 Professional Call WebSocket disconnected: {self.room_group_name}, code: {close_code}")
        
        # Leave room group
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        except:
            pass
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"📨 Received {message_type} from professional {self.professional_id}")
            
            # Handle different message types
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp'),
                    'received_at': timezone.now().isoformat()
                }))
                
            elif message_type == 'authenticate':
                # Handle authentication with token
                token = data.get('token')
                authenticated = await self.authenticate_user(token)
                
                if authenticated:
                    await self.send(text_data=json.dumps({
                        'type': 'authentication_success',
                        'message': 'Authenticated successfully',
                        'timestamp': timezone.now().isoformat()
                    }))
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'authentication_failed',
                        'message': 'Invalid authentication token',
                        'timestamp': timezone.now().isoformat()
                    }))
                    
            elif message_type == 'status_update':
                # Professional updating their online status
                status = data.get('status', 'online')
                await self.update_professional_status(status)
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'status_broadcast',
                        'status': status,
                        'professional_id': self.professional_id,
                        'timestamp': timezone.now().isoformat()
                    }
                )
                
            elif message_type == 'heartbeat':
                # Heartbeat to keep connection alive
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat_response',
                    'timestamp': timezone.now().isoformat(),
                    'client_timestamp': data.get('timestamp')
                }))
                
            else:
                # Unknown message type
                await self.send(text_data=json.dumps({
                    'type': 'unknown_message',
                    'received_type': message_type,
                    'timestamp': timezone.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format',
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            print(f"❌ Error processing WebSocket message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Server error: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }))
    
    # ========== INCOMING CALL NOTIFICATION ==========
    async def incoming_call_notification(self, event):
        """
        Send incoming call notification to professional
        This is triggered by Django when a client initiates a call
        """
        print(f"📞 Sending incoming call notification to professional {self.professional_id}")
        
        await self.send(text_data=json.dumps({
            'type': 'incoming_call',
            'session_id': event.get('session_id'),
            'call_id': event.get('call_id'),
            'client_id': event.get('client_id'),
            'client_name': event.get('client_name', 'Client'),
            'client_email': event.get('client_email', ''),
            'client_phone': event.get('client_phone', ''),
            'mode': event.get('mode', 'audio'),
            'category': event.get('category', ''),
            'urgency': event.get('urgency', 'medium'),
            'ringtone': event.get('ringtone', 'default'),
            'vibrate': event.get('vibrate', True),
            'timestamp': event.get('timestamp', timezone.now().isoformat()),
            'professional_id': self.professional_id
        }))
    
    # ========== CALL ACCEPTED ==========
    async def call_accepted_notification(self, event):
        """Notify that professional accepted the call"""
        await self.send(text_data=json.dumps({
            'type': 'call_accepted',
            'session_id': event.get('session_id'),
            'professional_id': event.get('professional_id'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # ========== CALL DECLINED ==========
    async def call_declined_notification(self, event):
        """Notify that professional declined the call"""
        await self.send(text_data=json.dumps({
            'type': 'call_declined',
            'session_id': event.get('session_id'),
            'professional_id': event.get('professional_id'),
            'reason': event.get('reason', 'Busy'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # ========== CALL ENDED ==========
    async def call_ended_notification(self, event):
        """Notify that call has ended"""
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'session_id': event.get('session_id'),
            'professional_id': event.get('professional_id'),
            'duration': event.get('duration', 0),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # ========== STATUS BROADCAST ==========
    async def status_broadcast(self, event):
        """Broadcast status update to all in room"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': event['status'],
            'professional_id': event['professional_id'],
            'timestamp': event['timestamp']
        }))
    
    # ========== NEW SESSION REQUEST ==========
    async def new_session_request(self, event):
        """New session request from client"""
        await self.send(text_data=json.dumps({
            'type': 'new_session_request',
            'session_id': event.get('session_id'),
            'client_id': event.get('client_id'),
            'client_name': event.get('client_name', 'Client'),
            'mode': event.get('mode', 'chat'),
            'category': event.get('category', ''),
            'urgency': event.get('urgency', 'medium'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # ========== SESSION STARTED ==========
    async def session_started_notification(self, event):
        """Session has started"""
        await self.send(text_data=json.dumps({
            'type': 'session_started',
            'session_id': event.get('session_id'),
            'client_id': event.get('client_id'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # ========== DATABASE OPERATIONS ==========
    @database_sync_to_async
    def authenticate_user(self, token):
        """Authenticate user using Django REST token"""
        try:
            token_obj = Token.objects.get(key=token)
            user = token_obj.user
            
            # Check if user is the professional
            professional_exists = Professional.objects.filter(
                id=self.professional_id,
                user=user
            ).exists()
            
            if professional_exists:
                print(f"✅ Professional {self.professional_id} authenticated successfully")
                return True
                
        except Token.DoesNotExist:
            print(f"❌ Invalid token for professional {self.professional_id}")
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
        
        return False
    
    @database_sync_to_async
    def update_professional_status(self, status):
        """Update professional status in database"""
        try:
            professional = Professional.objects.get(id=self.professional_id)
            professional.online_status = (status == 'online')
            professional.save()
            print(f"✅ Updated professional {self.professional_id} status to: {status}")
        except Professional.DoesNotExist:
            print(f"❌ Professional {self.professional_id} not found")
        except Exception as e:
            print(f"❌ Error updating status: {str(e)}")
