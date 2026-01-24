# routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebRTC signaling for specific session
    re_path(r'ws/webrtc/(?P<session_id>\w+)/$', consumers.WebRTCConsumer.as_asgi()),
    
    # General notifications
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    
    # Test endpoint
    re_path(r'ws/test/$', consumers.SimpleTestConsumer.as_asgi()),  # ✅ Correct: consumers.SimpleTestConsumer  # ✅ FIXED: changed consumers_test to consumers
]
