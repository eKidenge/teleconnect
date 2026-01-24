"""
ASGI config for teleconnect project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teleconnect.settings')

# Initialize Django BEFORE importing routing
django.setup()

# Now import routing after Django is initialized
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import quickconnect.routing
import webrtc.routing  # Make sure this exists!

# Combine WebSocket URL patterns
websocket_urlpatterns = []
websocket_urlpatterns += webrtc.routing.websocket_urlpatterns
websocket_urlpatterns += quickconnect.routing.websocket_urlpatterns

# Debug middleware
class DebugMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            print(f"🔌 WebSocket connection attempt: {scope.get('path', 'unknown')}")
            print(f"   Headers: {scope.get('headers', [])}")
        return await self.app(scope, receive, send)

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})

# Wrap with debug middleware in development
if os.environ.get('DEBUG', 'True') == 'True':
    application = DebugMiddleware(application)
