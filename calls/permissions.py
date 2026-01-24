from rest_framework import permissions
from .models import CallParticipant

class IsRoomParticipant(permissions.BasePermission):
    """Check if user is a participant in the room"""
    
    def has_object_permission(self, request, view, obj):
        return CallParticipant.objects.filter(
            room=obj,
            user=request.user,
            has_left=False
        ).exists()

class IsRoomHost(permissions.BasePermission):
    """Check if user is the host of the room"""
    
    def has_object_permission(self, request, view, obj):
        return obj.host == request.user

class IsCallParticipant(permissions.BasePermission):
    """Check if user can access call data"""
    
    def has_permission(self, request, view):
        if view.action in ['join', 'leave']:
            return True
        return request.user.is_authenticated
