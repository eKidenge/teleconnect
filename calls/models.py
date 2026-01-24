from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class CallRoom(models.Model):
    ROOM_TYPES = [
        ('audio', 'Audio Call'),
        ('video', 'Video Call'),
        ('voice', 'Voice Chat'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_name = models.CharField(max_length=200, blank=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_rooms')
    participants = models.ManyToManyField(User, through='CallParticipant', related_name='call_rooms')
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='video')
    is_active = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.room_name or 'Room'} ({self.get_room_type_display()})"
    
    def is_full(self):
        return self.active_participants.count() >= self.max_participants
    
    def end_call(self):
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()
        self.participants.update(has_left=True)

class CallParticipant(models.Model):
    ROLE_CHOICES = [
        ('host', 'Host'),
        ('participant', 'Participant'),
        ('viewer', 'Viewer'),
    ]
    
    room = models.ForeignKey(CallRoom, on_delete=models.CASCADE, related_name='room_participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_participations')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    is_video_off = models.BooleanField(default=False)
    has_left = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['room', 'user']
        ordering = ['joined_at']
    
    def leave(self):
        self.left_at = timezone.now()
        self.has_left = True
        self.save()
    
    @property
    def is_active(self):
        return self.has_left is False and self.left_at is None

class CallHistory(models.Model):
    CALL_TYPES = [
        ('audio', 'Audio Call'),
        ('video', 'Video Call'),
        ('group_audio', 'Group Audio'),
        ('group_video', 'Group Video'),
    ]
    
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(CallRoom, on_delete=models.SET_NULL, null=True, related_name='history')
    participants = models.ManyToManyField(User, related_name='call_history')
    initiator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='initiated_calls')
    call_type = models.CharField(max_length=20, choices=CALL_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name_plural = 'Call Histories'
    
    def save(self, *args, **kwargs):
        if self.ended_at and self.started_at:
            self.duration = self.ended_at - self.started_at
        super().save(*args, **kwargs)

class ZegoSettings(models.Model):
    """Store ZEGO credentials securely"""
    app_id = models.BigIntegerField()
    server_secret = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Ensure only one active setting
        if self.is_active:
            ZegoSettings.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_settings(cls):
        return cls.objects.filter(is_active=True).first()
