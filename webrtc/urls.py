from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'calls', views.WebRTCCallViewSet, basename='webrtc-call')
router.register(r'signals', views.CallSignalViewSet, basename='call-signal')
router.register(r'connections', views.PeerConnectionViewSet, basename='peer-connection')

urlpatterns = [
    path('', include(router.urls)),
    
    # WebSocket endpoints (handled by Channels routing)
    # These are for WebSocket connections, not HTTP
]

# WebSocket URLs are configured in routing.py