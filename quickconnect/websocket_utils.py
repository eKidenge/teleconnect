from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json

def notify_professional_of_call(professional_id, call_data):
    """
    Send incoming call notification to professional via WebSocket
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'calls_professional_{professional_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'incoming_call_notification',
                'session_id': call_data.get('session_id'),
                'call_id': call_data.get('call_id'),
                'client_id': call_data.get('client_id'),
                'client_name': call_data.get('client_name', 'Client'),
                'client_email': call_data.get('client_email', ''),
                'client_phone': call_data.get('client_phone', ''),
                'mode': call_data.get('mode', 'audio'),
                'category': call_data.get('category', ''),
                'urgency': call_data.get('urgency', 'medium'),
                'ringtone': call_data.get('ringtone', 'default'),
                'vibrate': call_data.get('vibrate', True),
                'timestamp': timezone.now().isoformat()
            }
        )
        
        print(f"📡 WebSocket notification sent to professional {professional_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending WebSocket notification: {str(e)}")
        return False

def notify_call_accepted(professional_id, session_id):
    """
    Notify that professional accepted the call
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'calls_professional_{professional_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'call_accepted_notification',
                'session_id': session_id,
                'professional_id': professional_id,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        return True
    except Exception as e:
        print(f"Error sending call accepted notification: {str(e)}")
        return False

def notify_call_declined(professional_id, session_id, reason='Busy'):
    """
    Notify that professional declined the call
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'calls_professional_{professional_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'call_declined_notification',
                'session_id': session_id,
                'professional_id': professional_id,
                'reason': reason,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        return True
    except Exception as e:
        print(f"Error sending call declined notification: {str(e)}")
        return False
