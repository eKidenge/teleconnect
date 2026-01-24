from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'calls', views.CallSessionViewSet, basename='call')
router.register(r'chat/threads', views.ChatThreadViewSet, basename='chatthread')
router.register(r'chat/messages', views.MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]
