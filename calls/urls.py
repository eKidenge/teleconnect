from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'rooms', views.CallRoomViewSet, basename='callroom')
router.register(r'history', views.CallHistoryViewSet, basename='callhistory')

urlpatterns = [
    # API Home
    path('', views.calls_api_home, name='calls-api-home'),
    
    # DRF ViewSets
    path('', include(router.urls)),
    
    # Token endpoints
    path('token/', views.ZegoTokenView.as_view(), name='zego-token'),
    path('token/public/', views.zego_token_public, name='zego-token-public'),
    
    # Active rooms
    path('active-rooms/', views.ActiveRoomsView.as_view(), name='active-rooms'),
    
    # Additional endpoints
    path('test-auth/', views.test_auth, name='test-auth'),
    path('user-stats/', views.user_call_stats, name='user-call-stats'),
    path('room/<uuid:room_id>/info/', views.room_info, name='room-info'),
    path('create-room-simple/', views.create_room_simple, name='create-room-simple'),
    
    # Room actions (compatible with DRF)
    path('rooms/<uuid:pk>/join/', views.CallRoomViewSet.as_view({'post': 'join'}), name='room-join'),
    path('rooms/<uuid:pk>/leave/', views.CallRoomViewSet.as_view({'post': 'leave'}), name='room-leave'),
    path('rooms/<uuid:pk>/participants/', views.CallRoomViewSet.as_view({'get': 'participants'}), name='room-participants'),
    path('rooms/<uuid:pk>/end/', views.CallRoomViewSet.as_view({'post': 'end_call'}), name='room-end'),
]
