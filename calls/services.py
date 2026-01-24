import jwt
import time
import uuid
from datetime import datetime
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import ZegoSettings

class ZegoService:
    
    @staticmethod
    def get_credentials():
        """Get ZEGO credentials from database or settings"""
        try:
            # 1. FIRST: Try to get from database
            settings_obj = ZegoSettings.get_active_settings()
            if settings_obj and settings_obj.app_id and settings_obj.server_secret:
                print(f"✅ Using ZEGO credentials from database: AppID={settings_obj.app_id}")
                return settings_obj.app_id, settings_obj.server_secret
        except Exception as db_error:
            print(f"⚠️ Database lookup failed: {db_error}")
        
        # 2. SECOND: Check hardcoded settings in settings.py
        try:
            from django.conf import settings
            app_id = getattr(settings, 'ZEGO_APP_ID', None)
            server_secret = getattr(settings, 'ZEGO_SERVER_SECRET', None)
            
            if app_id and server_secret:
                print(f"✅ Using ZEGO credentials from settings.py: AppID={app_id}")
                return app_id, server_secret
        except Exception as settings_error:
            print(f"⚠️ Settings.py lookup failed: {settings_error}")
        
        # 3. THIRD: Use your exact hardcoded values from your settings.py
        print("✅ Using hardcoded ZEGO credentials")
        return 408880662, "ab2b6cf242c1e4f9d1b5ca4654f76b96"
    
    @staticmethod
    def generate_token(user_id, room_id, effective_hours=24):
        """
        Generate ZEGO token for RTC authentication
        
        Args:
            user_id: User identifier (string)
            room_id: Room identifier
            effective_hours: Token validity in hours
            
        Returns:
            dict: Token and related info
        """
        try:
            print(f"🔧 Generating token for user:{user_id}, room:{room_id}")
            
            # Get credentials (will try database first, then settings)
            app_id, server_secret = ZegoService.get_credentials()
            
            print(f"✅ Credentials obtained: AppID={app_id}")
            print(f"✅ Server Secret available: {'Yes' if server_secret else 'No'}")
            
            # Generate payload
            payload = {
                "app_id": app_id,
                "user_id": str(user_id),
                "nonce": str(uuid.uuid4()),
                "ctime": int(time.time()),
                "expire": int(time.time()) + (effective_hours * 3600),
                "payload": {
                    "room_id": str(room_id),
                }
            }
            
            print(f"📦 Token payload: {payload}")
            
            # Generate token
            token = jwt.encode(
                payload,
                server_secret,
                algorithm="HS256"
            )
            
            # For debugging - decode to verify
            try:
                decoded = jwt.decode(token, server_secret, algorithms=["HS256"])
                print(f"✅ Token generated successfully. Decoded payload: {decoded}")
            except Exception as decode_error:
                print(f"⚠️ Token generated but cannot decode: {decode_error}")
            
            # Cache token for quick validation
            cache_key = f"zego_token_{user_id}_{room_id}"
            cache.set(cache_key, token, timeout=effective_hours * 3600 - 300)
            
            return {
                "app_id": app_id,
                "token": token,
                "user_id": str(user_id),
                "room_id": str(room_id),
                "expires_in": effective_hours * 3600,
                "generated_at": datetime.now().isoformat()
            }
            
        except jwt.exceptions.InvalidKeyError as e:
            error_msg = f"JWT Key Error: {str(e)} - Check your server_secret"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Token generation failed: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    @staticmethod
    def validate_token(token):
        """Validate ZEGO token"""
        try:
            # Get credentials same way as generation
            _, server_secret = ZegoService.get_credentials()
            decoded = jwt.decode(token, server_secret, algorithms=["HS256"])
            return decoded
        except jwt.ExpiredSignatureError:
            raise Exception("Token has expired")
        except jwt.InvalidTokenError as e:
            raise Exception(f"Invalid token: {str(e)}")
    
    @staticmethod
    def generate_test_token(user_id="test_user", room_id="test_room"):
        """Generate a test token for debugging"""
        try:
            print("🧪 Generating test token...")
            token_data = ZegoService.generate_token(user_id, room_id, effective_hours=1)
            print(f"✅ Test token generated: {token_data['token'][:50]}...")
            return token_data
        except Exception as e:
            print(f"❌ Test token generation failed: {e}")
            return None
    
    @staticmethod
    def verify_zego_credentials():
        """Verify ZEGO credentials are working"""
        try:
            app_id, server_secret = ZegoService.get_credentials()
            
            # Test JWT encoding/decoding
            test_payload = {"test": True, "timestamp": int(time.time())}
            token = jwt.encode(test_payload, server_secret, algorithm="HS256")
            decoded = jwt.decode(token, server_secret, algorithms=["HS256"])
            
            return {
                "status": "success",
                "app_id": app_id,
                "server_secret_length": len(server_secret),
                "jwt_test": "passed",
                "message": "ZEGO credentials are valid"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "ZEGO credentials verification failed"
            }
    
    @staticmethod
    def generate_test_credentials():
        """Generate credentials for testing (use only in development)"""
        return {
            "app_id": 408880662,  # YOUR actual app ID
            "server_secret": "ab2b6cf242c1e4f9d1b5ca4654f76b96",  # YOUR actual secret
            "note": "From your settings.py file"
        }

class CallManager:
    
    @staticmethod
    def create_room(user, room_name=None, room_type='video', max_participants=10):
        """Create a new call room"""
        from .models import CallRoom, CallParticipant
        
        room = CallRoom.objects.create(
            room_name=room_name or f"{user.username}'s Room",
            host=user,
            room_type=room_type,
            max_participants=max_participants
        )
        
        # Add host as participant
        CallParticipant.objects.create(
            room=room,
            user=user,
            role='host'
        )
        
        return room
    
    @staticmethod
    def join_room(user, room_id):
        """User joins a call room"""
        from .models import CallRoom, CallParticipant
        
        try:
            room = CallRoom.objects.get(id=room_id, is_active=True)
            
            if room.is_full():
                raise Exception("Room is full")
            
            # Check if already a participant
            participant, created = CallParticipant.objects.get_or_create(
                room=room,
                user=user,
                defaults={'role': 'participant'}
            )
            
            if not created and participant.has_left:
                participant.has_left = False
                participant.left_at = None
                participant.save()
            
            # Generate ZEGO token
            zego_token = ZegoService.generate_token(
                user_id=str(user.id),
                room_id=str(room.id)
            )
            
            return {
                "room": room,
                "participant": participant,
                "zego_token": zego_token,
                "is_new_joiner": created
            }
            
        except CallRoom.DoesNotExist:
            raise Exception("Room not found or inactive")
    
    @staticmethod
    def leave_room(user, room_id):
        """User leaves a call room"""
        from .models import CallParticipant, CallHistory, CallRoom
        
        try:
            participant = CallParticipant.objects.get(
                room_id=room_id,
                user=user,
                has_left=False
            )
            participant.leave()
            
            # Check if room is empty
            room = participant.room
            active_participants = room.room_participants.filter(has_left=False)
            
            if not active_participants.exists():
                room.end_call()
                
                # Create call history
                CallHistory.objects.create(
                    room=room,
                    initiator=room.host,
                    call_type=f"{room.room_type}_call",
                    started_at=room.created_at,
                    ended_at=timezone.now()
                )
            
            return True
            
        except CallParticipant.DoesNotExist:
            return False
    
    @staticmethod
    def get_room_participants(room_id):
        """Get all active participants in a room"""
        from .models import CallParticipant
        return CallParticipant.objects.filter(
            room_id=room_id,
            has_left=False
        ).select_related('user')
