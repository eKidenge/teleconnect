import time
import jwt
from django.conf import settings

class AgoraTokenGenerator:
    def __init__(self):
        self.app_id = settings.AGORA_APP_ID
        self.app_certificate = settings.AGORA_APP_CERTIFICATE
    
    def generate_rtc_token(self, channel_name, uid, role='publisher', expire_time=3600):
        privilege_expired_ts = int(time.time()) + expire_time
        
        token = jwt.encode(
            {
                'app_id': self.app_id,
                'exp': privilege_expired_ts,
                'iat': int(time.time()),
                'privileges': {
                    'join_channel': privilege_expired_ts,
                    'publish_audio': privilege_expired_ts if role == 'publisher' else 0,
                    'publish_video': privilege_expired_ts if role == 'publisher' else 0,
                }
            },
            self.app_certificate,
            algorithm='HS256'
        )
        
        return token


class AgoraChannelManager:
    @staticmethod
    def generate_channel_name(user1_id, user2_id):
        ids = sorted([str(user1_id), str(user2_id)])
        return f"call_{ids[0]}_{ids[1]}_{int(time.time())}"
    
    @staticmethod
    def parse_channel_name(channel_name):
        try:
            parts = channel_name.split('_')
            if len(parts) >= 3 and parts[0] == 'call':
                user1_id = int(parts[1])
                user2_id = int(parts[2])
                return user1_id, user2_id
        except:
            pass
        return None, None


agora_token_generator = AgoraTokenGenerator()
