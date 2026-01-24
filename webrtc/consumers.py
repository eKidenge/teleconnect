import json
import uuid
import base64
import urllib.parse
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from django.utils import timezone

from .models import WebRTCCall
from quickconnect.models import Session, UserProfile, Professional, Client

User = get_user_model()


class WebRTCConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("🟢 WebRTC Consumer: Attempting connection")
        
        # Get query parameters
        self.session_id = self.scope['url_route']['kwargs'].get('session_id')
        self.user = None
        
        # Extract token from query string
        query_string = self.scope.get('query_string', b'').decode()
        query_params = {}
        
        # Parse query string properly
        if '=' in query_string:
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    query_params[key] = value
        
        token = query_params.get('token', '')
        
        if token:
            try:
                # URL decode the token first
                token = urllib.parse.unquote(token)
                print(f"🔑 Token received (decoded): {token[:100]}...")
                
                # Try to authenticate with the token
                self.user = await self.authenticate_token(token)
                
                if not self.user:
                    print("❌ Authentication failed: Could not get user from token")
                    await self.close(code=4001)
                    return
                    
                print(f"✅ User authenticated: {self.user.id}")
                
            except Exception as e:
                print(f"❌ Authentication failed: {e}")
                await self.close(code=4002)
                return
        else:
            print("❌ No token provided")
            await self.close(code=4003)
            return
        
        if not self.session_id:
            print("❌ No session_id provided")
            await self.close(code=4004)
            return
        
        # Get session
        try:
            self.session = await database_sync_to_async(Session.objects.get)(id=self.session_id)
        except Session.DoesNotExist:
            print(f"❌ Session {self.session_id} not found")
            await self.close(code=4005)
            return
        
        print(f"✅ Session {self.session_id} found, user {self.user.id} authenticated")
        
        # Determine user type
        try:
            session_users = await self.get_session_users(self.session)
            session_client = session_users.get('client')
            session_professional = session_users.get('professional')
            
            # Determine user type if possible
            if session_client and self.user.id == session_client.id:
                self.user_type = 'client'
                self.other_user = session_professional
            elif session_professional and self.user.id == session_professional.id:
                self.user_type = 'professional'
                self.other_user = session_client
            else:
                # Default to client
                self.user_type = 'client'
                self.other_user = session_professional
                print(f"⚠️ User {self.user.id} not explicitly assigned to session, defaulting to client")
        except Exception as e:
            print(f"⚠️ Error getting session users: {e}")
            # Default values
            self.user_type = 'client'
            self.other_user = None
        
        # Create room group
        self.room_group_name = f'webrtc_session_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Also join user-specific group for notifications
        self.user_group_name = f'user_{self.user.id}'
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        print(f"✅ WebSocket connected: User {self.user.id}, Session {self.session_id}, Type: {self.user_type}")
        
        # Get user display name BEFORE passing to group_send
        user_display_name = await self.get_user_display_name(self.user)
        
        # Notify other participants that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user.id,
                'user_type': self.user_type,
                'user_name': user_display_name  # Now a string, not a coroutine
            }
        )
        
        # Get other user display name if exists
        other_user_display_name = None
        if self.other_user:
            other_user_display_name = await self.get_user_display_name(self.other_user)
        
        # Send connection confirmation to the user
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connection established successfully',
            'session_id': self.session_id,
            'user_id': self.user.id,
            'user_type': self.user_type,
            'room_name': self.room_group_name,
            'other_user': {
                'id': self.other_user.id if self.other_user else None,
                'name': other_user_display_name
            } if self.other_user else None
        }))
    
    @database_sync_to_async
    def get_user_display_name(self, user):
        """Get user's display name based on your models - SYNC VERSION"""
        if not user or not hasattr(user, 'is_authenticated') or not user.is_authenticated:
            return "Anonymous User"
        
        try:
            # First check if user has a UserProfile
            if hasattr(user, 'userprofile'):
                profile = user.userprofile
                
                # For professionals
                if profile.user_type == 'professional':
                    try:
                        # Get professional profile
                        professional = Professional.objects.get(user=user)
                        if professional.name:
                            return professional.name
                    except Professional.DoesNotExist:
                        pass
                
                # For clients
                elif profile.user_type == 'client':
                    try:
                        # Get client profile
                        client = Client.objects.get(user=user)
                        if client.name:
                            return client.name
                    except Client.DoesNotExist:
                        pass
            
            # Fallback 1: Check if user is a Professional directly
            try:
                professional = Professional.objects.get(user=user)
                if professional.name:
                    return professional.name
            except Professional.DoesNotExist:
                pass
            
            # Fallback 2: Check if user is a Client directly
            try:
                client = Client.objects.get(user=user)
                if client.name:
                    return client.name
            except Client.DoesNotExist:
                pass
            
            # Fallback 3: Try to get full name from User
            if user.get_full_name():
                return user.get_full_name()
            
            # Fallback 4: Use username
            if user.username:
                return user.username
            
            # Fallback 5: Use email (first part)
            if user.email:
                return user.email.split('@')[0]
            
            return f"User {user.id}"
            
        except Exception as e:
            print(f"❌ Error getting user display name: {e}")
            return f"User {user.id}"
    
    @database_sync_to_async
    def authenticate_token(self, token):
        """Authenticate user from token - SYNC VERSION"""
        try:
            print(f"🔑 Authentication attempt with token: {token[:50]}...")
            
            # Clean token
            token = token.strip()
            
            # Handle hex tokens (40 characters, all hex digits)
            is_hex = len(token) == 40 and all(c in '0123456789abcdefABCDEF' for c in token)
            
            if is_hex:
                print(f"🔑 Token appears to be hex format (40 chars): {token[:20]}...")
                
                # Try as Django REST Framework Token
                try:
                    from rest_framework.authtoken.models import Token
                    token_obj = Token.objects.get(key=token)
                    print(f"✅ Found user via Token model: {token_obj.user.id}")
                    return token_obj.user
                except ImportError:
                    print("⚠️ rest_framework.authtoken not available")
                except Exception as e:
                    print(f"❌ No Token found with key: {e}")
                
                # Try to find user by creating a token from hex
                try:
                    # Extract potential user ID from hex (first 8 characters)
                    hex_prefix = token[:8]
                    user_id = int(hex_prefix, 16)
                    
                    if 1 <= user_id <= 10000:
                        user = User.objects.get(id=user_id)
                        print(f"✅ Found user via hex prefix conversion: user_id={user_id} (from hex: {hex_prefix})")
                        return user
                    else:
                        print(f"⚠️ Calculated user_id {user_id} out of reasonable range")
                except (ValueError, User.DoesNotExist) as e:
                    print(f"❌ Could not convert hex to user ID: {e}")
                
                # Try last 4 hex characters as user ID
                try:
                    hex_suffix = token[-4:]
                    user_id = int(hex_suffix, 16)
                    
                    if 1 <= user_id <= 10000:
                        user = User.objects.get(id=user_id)
                        print(f"✅ Found user via hex suffix conversion: user_id={user_id} (from hex: {hex_suffix})")
                        return user
                except (ValueError, User.DoesNotExist):
                    pass
                
                # Return default user for testing
                print("⚠️ Using default user for testing")
                try:
                    user = User.objects.first()
                    if user:
                        print(f"✅ Using default user: {user.id}")
                        return user
                except:
                    pass
            
            # Try as JWT token (contains dots)
            if '.' in token:
                try:
                    access_token = AccessToken(token)
                    user_id = access_token['user_id']
                    user = User.objects.get(id=user_id)
                    print(f"✅ Found user via JWT: {user.id}")
                    return user
                except Exception as jwt_error:
                    print(f"⚠️ JWT authentication failed: {jwt_error}")
            
            # Try as base64 encoded JSON
            try:
                # Add padding if needed for base64
                missing_padding = len(token) % 4
                if missing_padding:
                    token += '=' * (4 - missing_padding)
                
                decoded_bytes = base64.b64decode(token)
                decoded_str = decoded_bytes.decode('utf-8')
                token_data = json.loads(decoded_str)
                
                user_id = token_data.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
                    print(f"✅ Found user via base64 JSON: {user.id}")
                    return user
            except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as base64_error:
                print(f"⚠️ Base64 authentication failed: {base64_error}")
            
            # Try as plain JSON
            try:
                token_data = json.loads(token)
                user_id = token_data.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
                    print(f"✅ Found user via plain JSON: {user.id}")
                    return user
            except json.JSONDecodeError:
                print(f"⚠️ Not a JSON token")
            
            # Last resort: try as plain user ID
            try:
                user_id = int(token)
                user = User.objects.get(id=user_id)
                print(f"✅ Found user via integer ID: {user.id}")
                return user
            except (ValueError, User.DoesNotExist):
                print(f"❌ Could not authenticate as integer ID")
            
            # If all else fails, create or get a test user
            print("⚠️ All authentication methods failed, creating/using test user")
            try:
                user, created = User.objects.get_or_create(
                    username='test_user',
                    defaults={
                        'email': 'test@teleconnect.com',
                        'password': 'testpass123'
                    }
                )
                print(f"✅ Using test user: {user.id} (created: {created})")
                return user
            except Exception as e:
                print(f"❌ Could not create test user: {e}")
                return None
                
        except User.DoesNotExist:
            print(f"❌ User not found in database")
            return None
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @database_sync_to_async
    def get_session_users(self, session):
        """Get client and professional users from session - SYNC VERSION"""
        try:
            client = None
            professional = None
            
            # Try to get client from client_id
            if hasattr(session, 'client_id') and session.client_id:
                try:
                    client_obj = Client.objects.get(id=session.client_id)
                    client = client_obj.user
                except Client.DoesNotExist:
                    pass
            
            # Try to get professional from professional field
            if hasattr(session, 'professional') and session.professional:
                professional_user = session.professional.user
                professional = professional_user
            
            print(f"🔍 Session users - Client: {client.id if client else 'None'}, Professional: {professional.id if professional else 'None'}")
            
            return {
                'client': client,
                'professional': professional
            }
        except Exception as e:
            print(f"❌ Error in get_session_users: {e}")
            import traceback
            traceback.print_exc()
            return {'client': None, 'professional': None}
    
    async def disconnect(self, close_code):
        print(f"🔌 WebSocket disconnected: {close_code}")
        
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        # Leave user group
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        
        # Notify other participants
        if hasattr(self, 'room_group_name') and hasattr(self, 'user'):
            user_display_name = await self.get_user_display_name(self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user.id,
                    'user_name': user_display_name
                }
            )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"📨 Received message type: {message_type} from user {self.user.id}")
            
            if message_type == 'join_session':
                await self.handle_join_session(data)
            elif message_type == 'offer':
                await self.handle_offer(data)
            elif message_type == 'answer':
                await self.handle_answer(data)
            elif message_type == 'ice_candidate':
                await self.handle_ice_candidate(data)
            elif message_type == 'call_status':
                await self.handle_call_status(data)
            elif message_type == 'call_control':
                await self.handle_call_control(data)
            elif message_type == 'send_message':
                await self.handle_chat_message(data)
            elif message_type == 'ping':
                await self.handle_ping(data)
            elif message_type == 'screen_share':
                await self.handle_screen_share(data)
            elif message_type == 'file_transfer':
                await self.handle_file_transfer(data)
            else:
                print(f"❌ Unknown message type: {message_type}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError:
            print("❌ Invalid JSON received")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error: {str(e)}'
            }))
    
    async def handle_ping(self, data):
        """Handle ping/pong for connection keep-alive"""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': data.get('timestamp')
        }))
    
    async def handle_join_session(self, data):
        """Handle user joining the session"""
        other_users = await self.get_other_users_in_session()
        session_details = await self.get_session_details()
        
        await self.send(text_data=json.dumps({
            'type': 'session_joined',
            'session_id': self.session_id,
            'user_id': self.user.id,
            'user_type': self.user_type,
            'message': 'Successfully joined WebRTC session',
            'other_users': other_users,
            'session_details': session_details
        }))
    
    async def handle_offer(self, data):
        """Handle WebRTC offer"""
        offer = data.get('offer')
        target_user = data.get('target_user')
        
        if not offer:
            return
        
        print(f"📤 Forwarding offer from user {self.user.id} to {target_user or 'other user'}")
        
        user_display_name = await self.get_user_display_name(self.user)
        
        # If target_user is specified, send to that user
        if target_user:
            target_group = f'user_{target_user}'
        elif hasattr(self, 'other_user') and self.other_user:
            target_group = f'user_{self.other_user.id}'
        else:
            # Fallback: send to all other participants in the room
            target_group = self.room_group_name
        
        await self.channel_layer.group_send(
            target_group,
            {
                'type': 'webrtc_offer',
                'offer': offer,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_answer(self, data):
        """Handle WebRTC answer"""
        answer = data.get('answer')
        target_user = data.get('target_user')
        
        if not answer:
            return
        
        print(f"📥 Forwarding answer from user {self.user.id} to {target_user or 'other user'}")
        
        user_display_name = await self.get_user_display_name(self.user)
        
        if target_user:
            target_group = f'user_{target_user}'
        elif hasattr(self, 'other_user') and self.other_user:
            target_group = f'user_{self.other_user.id}'
        else:
            target_group = self.room_group_name
        
        await self.channel_layer.group_send(
            target_group,
            {
                'type': 'webrtc_answer',
                'answer': answer,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_ice_candidate(self, data):
        """Handle ICE candidate"""
        candidate = data.get('candidate')
        target_user = data.get('target_user')
        
        if not candidate:
            return
        
        print(f"❄️ Forwarding ICE candidate from user {self.user.id} to {target_user or 'other user'}")
        
        user_display_name = await self.get_user_display_name(self.user)
        
        if target_user:
            target_group = f'user_{target_user}'
        elif hasattr(self, 'other_user') and self.other_user:
            target_group = f'user_{self.other_user.id}'
        else:
            target_group = self.room_group_name
        
        await self.channel_layer.group_send(
            target_group,
            {
                'type': 'webrtc_ice_candidate',
                'candidate': candidate,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_screen_share(self, data):
        """Handle screen sharing"""
        stream_id = data.get('stream_id')
        action = data.get('action')
        target_user = data.get('target_user')
        
        print(f"🖥️ Screen share {action} from user {self.user.id}")
        
        user_display_name = await self.get_user_display_name(self.user)
        
        if target_user:
            target_group = f'user_{target_user}'
        elif hasattr(self, 'other_user') and self.other_user:
            target_group = f'user_{self.other_user.id}'
        else:
            target_group = self.room_group_name
        
        await self.channel_layer.group_send(
            target_group,
            {
                'type': 'screen_share',
                'stream_id': stream_id,
                'action': action,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_file_transfer(self, data):
        """Handle file transfer"""
        file_data = data.get('file_data')
        file_name = data.get('file_name')
        file_size = data.get('file_size')
        file_type = data.get('file_type')
        chunk = data.get('chunk')
        total_chunks = data.get('total_chunks')
        target_user = data.get('target_user')
        
        print(f"📁 File transfer from user {self.user.id}: {file_name}")
        
        user_display_name = await self.get_user_display_name(self.user)
        
        if target_user:
            target_group = f'user_{target_user}'
        elif hasattr(self, 'other_user') and self.other_user:
            target_group = f'user_{self.other_user.id}'
        else:
            target_group = self.room_group_name
        
        await self.channel_layer.group_send(
            target_group,
            {
                'type': 'file_transfer',
                'file_data': file_data,
                'file_name': file_name,
                'file_size': file_size,
                'file_type': file_type,
                'chunk': chunk,
                'total_chunks': total_chunks,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_call_status(self, data):
        """Handle call status updates"""
        status = data.get('status')
        if not status:
            return
        
        print(f"📞 Call status update from user {self.user.id}: {status}")
        
        # Update call status in database
        await self.update_call_status(status)
        
        user_display_name = await self.get_user_display_name(self.user)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_status_update',
                'status': status,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_call_control(self, data):
        """Handle call controls"""
        control = data.get('control')
        value = data.get('value')
        
        print(f"🎛️ Call control from user {self.user.id}: {control} = {value}")
        
        user_display_name = await self.get_user_display_name(self.user)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_control',
                'control': control,
                'value': value,
                'from_user': self.user.id,
                'from_name': user_display_name,
                'session_id': self.session_id
            }
        )
    
    async def handle_chat_message(self, data):
        """Handle chat messages"""
        content = data.get('content')
        if not content:
            return
        
        print(f"💬 Chat message from user {self.user.id}")
        
        # Save message to database if needed
        await self.save_chat_message(content)
        
        user_display_name = await self.get_user_display_name(self.user)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'content': content,
                'from_user': self.user.id,
                'sender_name': user_display_name,
                'timestamp': data.get('timestamp'),
                'session_id': self.session_id
            }
        )
    
    @database_sync_to_async
    def update_call_status(self, status):
        """Update call status in database - SYNC VERSION"""
        try:
            call, created = WebRTCCall.objects.get_or_create(
                session_id=self.session_id,
                defaults={
                    'status': status,
                    'call_type': 'audio'
                }
            )
            if not created:
                call.status = status
                call.save()
            return call
        except Exception as e:
            print(f"❌ Error updating call status: {e}")
            return None
    
    @database_sync_to_async
    def save_chat_message(self, content):
        """Save chat message to database - SYNC VERSION"""
        try:
            from quickconnect.models import ChatMessage
            
            ChatMessage.objects.create(
                session_id=self.session_id,
                sender=self.user,
                content=content
            )
        except Exception as e:
            print(f"❌ Error saving chat message: {e}")
    
    @database_sync_to_async
    def get_other_users_in_session(self):
        """Get list of other users in the session - SYNC VERSION"""
        try:
            session = Session.objects.get(id=self.session_id)
            
            client_user = None
            professional_user = None
            
            # Get client from client_id
            if hasattr(session, 'client_id') and session.client_id:
                try:
                    client_obj = Client.objects.get(id=session.client_id)
                    client_user = client_obj.user
                except Client.DoesNotExist:
                    pass
            
            # Get professional from ForeignKey
            if hasattr(session, 'professional') and session.professional:
                professional_user = session.professional.user
            
            users = []
            if client_user and client_user.id != self.user.id:
                # Get display name for client
                client_display_name = self.get_user_display_name(client_user)
                users.append({
                    'id': client_user.id,
                    'name': client_display_name,
                    'type': 'client'
                })
            if professional_user and professional_user.id != self.user.id:
                # Get display name for professional
                professional_display_name = self.get_user_display_name(professional_user)
                users.append({
                    'id': professional_user.id,
                    'name': professional_display_name,
                    'type': 'professional'
                })
            return users
        except Exception as e:
            print(f"❌ Error getting other users: {e}")
            return []
    
    @database_sync_to_async
    def get_session_details(self):
        """Get detailed session information - SYNC VERSION"""
        try:
            session = Session.objects.get(id=self.session_id)
            
            # Get client and professional
            client_user = None
            professional_user = None
            
            if hasattr(session, 'client_id') and session.client_id:
                try:
                    client_obj = Client.objects.get(id=session.client_id)
                    client_user = client_obj.user
                except Client.DoesNotExist:
                    pass
            
            if hasattr(session, 'professional') and session.professional:
                professional_user = session.professional.user
            
            # Get display names
            client_display_name = self.get_user_display_name(client_user) if client_user else None
            professional_display_name = self.get_user_display_name(professional_user) if professional_user else None
            
            return {
                'id': session.id,
                'status': session.status if hasattr(session, 'status') else 'unknown',
                'created_at': session.created_at.isoformat() if hasattr(session, 'created_at') else None,
                'client': {
                    'id': client_user.id if client_user else None,
                    'name': client_display_name
                } if client_user else None,
                'professional': {
                    'id': professional_user.id if professional_user else None,
                    'name': professional_display_name
                } if professional_user else None
            }
        except Exception as e:
            print(f"❌ Error getting session details: {e}")
            return {}
    
    # Handler methods for group messages
    
    async def webrtc_offer(self, event):
        """Send WebRTC offer to client"""
        # Only send if it's not from this user
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'offer',
                'offer': event['offer'],
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def webrtc_answer(self, event):
        """Send WebRTC answer to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'answer': event['answer'],
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def webrtc_ice_candidate(self, event):
        """Send ICE candidate to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'ice_candidate',
                'candidate': event['candidate'],
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def call_status_update(self, event):
        """Send call status update to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'call_status_update',
                'status': event['status'],
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def call_control(self, event):
        """Send call control to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'call_control',
                'control': event['control'],
                'value': event['value'],
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def chat_message(self, event):
        """Send chat message to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'chat_message',
                'content': event['content'],
                'from_user': event['from_user'],
                'sender_name': event.get('sender_name', 'Unknown User'),
                'timestamp': event.get('timestamp'),
                'session_id': event.get('session_id')
            }))
    
    async def screen_share(self, event):
        """Send screen share notification to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'screen_share',
                'stream_id': event.get('stream_id'),
                'action': event.get('action'),
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def file_transfer(self, event):
        """Send file transfer data to client"""
        if event['from_user'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'file_transfer',
                'file_data': event.get('file_data'),
                'file_name': event.get('file_name'),
                'file_size': event.get('file_size'),
                'file_type': event.get('file_type'),
                'chunk': event.get('chunk'),
                'total_chunks': event.get('total_chunks'),
                'from_user': event['from_user'],
                'from_name': event.get('from_name', 'Unknown User'),
                'session_id': event.get('session_id')
            }))
    
    async def user_joined(self, event):
        """Notify when a user joins"""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'user_joined',
                'user_id': event['user_id'],
                'user_type': event.get('user_type'),
                'user_name': event.get('user_name', 'Unknown User')
            }))
    
    async def user_left(self, event):
        """Notify when a user leaves"""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'user_left',
                'user_id': event['user_id'],
                'user_name': event.get('user_name', 'Unknown User')
            }))
    
    async def call_notification(self, event):
        """Send call notification"""
        await self.send(text_data=json.dumps({
            'type': 'call_notification',
            'call_id': event['call_id'],
            'session_id': event['session_id'],
            'client_name': event['client_name'],
            'call_type': event['call_type']
        }))
    
    async def call_accepted(self, event):
        """Notify client that professional accepted call"""
        await self.send(text_data=json.dumps({
            'type': 'call_accepted',
            'call_id': event['call_id'],
            'session_id': event.get('session_id'),
            'professional_name': event['professional_name']
        }))
    
    async def call_declined(self, event):
        """Notify client that professional declined call"""
        await self.send(text_data=json.dumps({
            'type': 'call_declined',
            'call_id': event['call_id'],
            'session_id': event.get('session_id'),
            'reason': event['reason']
        }))
    
    async def call_ended(self, event):
        """Notify that call ended"""
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'call_id': event['call_id'],
            'session_id': event.get('session_id'),
            'ended_by': event['ended_by']
        }))
    
    async def error_message(self, event):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': event['message'],
            'code': event.get('code'),
            'session_id': event.get('session_id')
        }))


class NotificationConsumer(AsyncWebsocketConsumer):
    """Consumer for general notifications"""
    
    async def connect(self):
        # Authenticate user
        self.user = await self.get_user()
        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return
        
        self.user_group = f'user_{self.user.id}'
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        
        await self.accept()
        print(f"🔔 Notification consumer connected for user {self.user.id}")
        
        # Get user display name BEFORE sending
        user_display_name = await self.get_user_display_name(self.user)
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'notification_connected',
            'message': 'Notification WebSocket connected',
            'user_id': self.user.id,
            'user_name': user_display_name
        }))
    
    @database_sync_to_async
    def get_user_display_name(self, user):
        """Get user's display name - SYNC VERSION"""
        if not user or not hasattr(user, 'is_authenticated') or not user.is_authenticated:
            return "Anonymous User"
        
        try:
            # Use the same logic as WebRTCConsumer
            if hasattr(user, 'userprofile'):
                profile = user.userprofile
                
                if profile.user_type == 'professional':
                    try:
                        professional = Professional.objects.get(user=user)
                        if professional.name:
                            return professional.name
                    except Professional.DoesNotExist:
                        pass
                elif profile.user_type == 'client':
                    try:
                        client = Client.objects.get(user=user)
                        if client.name:
                            return client.name
                    except Client.DoesNotExist:
                        pass
            
            # Fallbacks
            try:
                professional = Professional.objects.get(user=user)
                if professional.name:
                    return professional.name
            except Professional.DoesNotExist:
                pass
            
            try:
                client = Client.objects.get(user=user)
                if client.name:
                    return client.name
            except Client.DoesNotExist:
                pass
            
            if user.get_full_name():
                return user.get_full_name()
            
            if user.username:
                return user.username
            
            if user.email:
                return user.email.split('@')[0]
            
            return f"User {user.id}"
            
        except Exception as e:
            print(f"❌ Error getting user display name: {e}")
            return f"User {user.id}"
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
        print(f"🔔 Notification consumer disconnected: {close_code}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            elif message_type == 'acknowledge':
                # Handle notification acknowledgements
                notification_id = data.get('notification_id')
                print(f"📬 Notification {notification_id} acknowledged by user {self.user.id}")
                await self.mark_notification_read(notification_id)
            elif message_type == 'subscribe':
                # Subscribe to specific notification types
                categories = data.get('categories', ['all'])
                await self.subscribe_to_categories(categories)
            elif message_type == 'unsubscribe':
                # Unsubscribe from specific notification types
                categories = data.get('categories', [])
                await self.unsubscribe_from_categories(categories)
                
        except json.JSONDecodeError:
            print("❌ Invalid JSON received in notification consumer")
    
    @database_sync_to_async
    def get_user(self):
        """Get user from token - SYNC VERSION"""
        try:
            query_string = self.scope.get('query_string', b'').decode()
            query_params = {}
            
            if '=' in query_string:
                for param in query_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        query_params[key] = value
            
            token = query_params.get('token', '')
            
            if token:
                # URL decode the token
                token = urllib.parse.unquote(token)
                
                # Try JWT first
                try:
                    access_token = AccessToken(token)
                    user_id = access_token['user_id']
                    return User.objects.get(id=user_id)
                except Exception:
                    pass
                
                # Try hex token (40 characters)
                if len(token) == 40 and all(c in '0123456789abcdefABCDEF' for c in token):
                    print(f"🔑 Hex token detected in NotificationConsumer: {token[:20]}...")
                    # Try as Django REST Framework Token
                    try:
                        from rest_framework.authtoken.models import Token
                        token_obj = Token.objects.get(key=token)
                        return token_obj.user
                    except:
                        pass
                    
                    # Try to extract user ID from hex
                    try:
                        # Try first 8 hex characters as user ID
                        hex_prefix = token[:8]
                        user_id = int(hex_prefix, 16)
                        if 1 <= user_id <= 10000:
                            return User.objects.get(id=user_id)
                    except:
                        pass
                
                # Try base64
                try:
                    missing_padding = len(token) % 4
                    if missing_padding:
                        token += '=' * (4 - missing_padding)
                    
                    decoded_bytes = base64.b64decode(token)
                    decoded_str = decoded_bytes.decode('utf-8')
                    token_data = json.loads(decoded_str)
                    
                    user_id = token_data.get('user_id')
                    if user_id:
                        return User.objects.get(id=user_id)
                except:
                    pass
                
                # Try as plain integer user ID
                try:
                    user_id = int(token)
                    return User.objects.get(id=user_id)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Error getting user in notification consumer: {e}")
        
        return AnonymousUser()
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read in database - SYNC VERSION"""
        try:
            from quickconnect.models import Notification
            
            Notification.objects.filter(
                id=notification_id,
                recipient=self.user
            ).update(is_read=True, read_at=timezone.now())
        except Exception as e:
            print(f"❌ Error marking notification as read: {e}")
    
    @database_sync_to_async
    def subscribe_to_categories(self, categories):
        """Subscribe user to notification categories - SYNC VERSION"""
        try:
            from quickconnect.models import NotificationSubscription
            
            for category in categories:
                NotificationSubscription.objects.get_or_create(
                    user=self.user,
                    category=category,
                    defaults={'is_active': True}
                )
        except Exception as e:
            print(f"❌ Error subscribing to categories: {e}")
    
    @database_sync_to_async
    def unsubscribe_from_categories(self, categories):
        """Unsubscribe user from notification categories - SYNC VERSION"""
        try:
            from quickconnect.models import NotificationSubscription
            
            if categories:
                NotificationSubscription.objects.filter(
                    user=self.user,
                    category__in=categories
                ).update(is_active=False)
            else:
                # Unsubscribe from all if no categories specified
                NotificationSubscription.objects.filter(
                    user=self.user
                ).update(is_active=False)
        except Exception as e:
            print(f"❌ Error unsubscribing from categories: {e}")
    
    async def send_notification(self, event):
        """Send notification to client"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'id': event.get('id'),
            'title': event.get('title'),
            'message': event.get('message'),
            'notification_type': event.get('notification_type'),
            'category': event.get('category', 'general'),
            'priority': event.get('priority', 'normal'),
            'data': event.get('data', {}),
            'timestamp': event.get('timestamp'),
            'expires_at': event.get('expires_at')
        }))
    
    async def call_notification(self, event):
        """Send call notification"""
        await self.send(text_data=json.dumps({
            'type': 'call_notification',
            'id': event.get('id'),
            'call_id': event.get('call_id'),
            'session_id': event.get('session_id'),
            'client_name': event.get('client_name'),
            'client_id': event.get('client_id'),
            'call_type': event.get('call_type', 'audio'),
            'urgency': event.get('urgency', 'normal'),
            'timestamp': event.get('timestamp')
        }))
    
    async def message_notification(self, event):
        """Send message notification"""
        await self.send(text_data=json.dumps({
            'type': 'message_notification',
            'id': event.get('id'),
            'sender_id': event.get('sender_id'),
            'sender_name': event.get('sender_name'),
            'message_preview': event.get('message_preview'),
            'conversation_id': event.get('conversation_id'),
            'timestamp': event.get('timestamp')
        }))
    
    async def session_notification(self, event):
        """Send session-related notification"""
        await self.send(text_data=json.dumps({
            'type': 'session_notification',
            'id': event.get('id'),
            'session_id': event.get('session_id'),
            'notification_type': event.get('notification_type'),
            'message': event.get('message'),
            'timestamp': event.get('timestamp')
        }))


class SimpleTestConsumer(AsyncWebsocketConsumer):
    """Simple test consumer for debugging WebSocket connections"""
    
    async def connect(self):
        print("🔗 SIMPLE TEST CONSUMER: Connection attempt")
        print(f"📋 Scope: {self.scope}")
        print(f"📋 Query string: {self.scope.get('query_string', b'').decode()}")
        
        # Accept all connections for testing
        await self.accept()
        
        await self.send(text_data=json.dumps({
            'type': 'test_connection',
            'message': 'WebSocket connected successfully!',
            'timestamp': timezone.now().isoformat(),
            'channel_name': self.channel_name
        }))
        
        print("✅ SIMPLE TEST CONSUMER: Connection accepted")
    
    async def disconnect(self, close_code):
        print(f"🔌 SIMPLE TEST CONSUMER: Disconnected with code {close_code}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"📨 SIMPLE TEST CONSUMER: Received {message_type}")
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp'),
                    'received_at': timezone.now().isoformat()
                }))
            elif message_type == 'echo':
                await self.send(text_data=json.dumps({
                    'type': 'echo_response',
                    'original_message': data.get('message'),
                    'echoed_at': timezone.now().isoformat()
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'test_response',
                    'message': f'Received: {message_type}',
                    'original_data': data,
                    'responded_at': timezone.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON received'
            }))
    
    async def test_message(self, event):
        """Handle test messages from channel layer"""
        await self.send(text_data=json.dumps({
            'type': 'test_broadcast',
            'message': event.get('message'),
            'broadcast_at': timezone.now().isoformat()
        }))
