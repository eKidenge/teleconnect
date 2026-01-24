from django.urls import re_path
from . import consumers
from webrtc import consumers as webrtc_consumers  # Import webrtc consumers

websocket_urlpatterns = [
    # Quick Connect - Professional matching
    re_path(r'ws/quick-connect/$', consumers.QuickConnectConsumer.as_asgi()),
    re_path(r'ws/quickconnect/$', consumers.QuickConnectConsumer.as_asgi()),
    
    # Session management (multiple patterns)
    re_path(r'ws/session/(?P<professional_id>\d+)/(?P<client_id>[^/]+)/$', consumers.SessionConsumer.as_asgi()),
    re_path(r'ws/session/(?P<session_id>\w+)/$', consumers.SessionConsumer.as_asgi()),
    
    # 🔥 USE WEBRTC FOR VIDEO CALLS
    re_path(r'ws/webrtc/(?P<session_id>\w+)/$', webrtc_consumers.WebRTCConsumer.as_asgi()),
    
    # Call management - also use webrtc
    re_path(r'ws/call/(?P<session_id>\w+)/$', webrtc_consumers.WebRTCConsumer.as_asgi()),
    
    # 🔥 PROFESSIONAL CALL NOTIFICATIONS
    re_path(r'ws/calls/(?P<professional_id>\d+)/$', consumers.ProfessionalCallNotificationConsumer.as_asgi()),
    
    # Notifications - KEEP COMMENTED OUT
    # re_path(r'ws/notifications/(?P<user_id>\d+)/$', consumers.NotificationConsumer.as_asgi()),
]
