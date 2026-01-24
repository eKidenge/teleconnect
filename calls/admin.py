from django.contrib import admin
from .models import CallRoom, CallParticipant, CallHistory, ZegoSettings

@admin.register(CallRoom)
class CallRoomAdmin(admin.ModelAdmin):
    list_display = ['room_name', 'host', 'room_type', 'is_active', 'created_at']
    list_filter = ['room_type', 'is_active']
    search_fields = ['room_name', 'host__username']

@admin.register(CallParticipant)
class CallParticipantAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'role', 'joined_at', 'has_left']
    list_filter = ['role', 'has_left']
    search_fields = ['user__username', 'room__room_name']

@admin.register(CallHistory)
class CallHistoryAdmin(admin.ModelAdmin):
    list_display = ['call_type', 'status', 'initiator', 'started_at', 'duration']
    list_filter = ['call_type', 'status']
    search_fields = ['initiator__username']

@admin.register(ZegoSettings)
class ZegoSettingsAdmin(admin.ModelAdmin):
    list_display = ['app_id', 'is_active', 'created_at']
    list_editable = ['is_active']
