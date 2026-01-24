from django.db import models
from django.conf import settings
import uuid
from django.utils import timezone

# ========== CALLS MODELS ==========
class CallSession(models.Model):
    CALL_TYPE_CHOICES = (
        ('voice', 'Voice Call'),
        ('video', 'Video Call'),
    )
    
    STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('missed', 'Missed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                               related_name='calls_made')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                 related_name='calls_received')
    
    # Call details
    call_type = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES, default='voice')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    channel_name = models.CharField(max_length=255, unique=True)
    
    # Timing
    initiated_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # in seconds
    
    # Agora specific
    agora_channel = models.CharField(max_length=255)
    agora_token = models.TextField()
    
    # Session info
    session_id = models.CharField(max_length=255, null=True, blank=True)
    call_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['caller', 'status']),
            models.Index(fields=['receiver', 'status']),
            models.Index(fields=['channel_name']),
        ]
    
    @property
    def call_cost(self):
        """Calculate call cost based on duration"""
        minutes = self.duration / 60
        return round(float(minutes * self.call_rate), 2)
    
    def end_call(self, duration_seconds):
        """Mark call as completed"""
        self.status = 'completed'
        self.duration = duration_seconds
        self.ended_at = timezone.now()
        self.save()


class CallLog(models.Model):
    """Store call events for analytics"""
    call_session = models.ForeignKey(CallSession, on_delete=models.CASCADE, related_name='logs')
    event_type = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-timestamp']


# ========== CHAT MODELS ==========
class ChatThread(models.Model):
    """Thread between two users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                             related_name='threads_as_user1')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                             related_name='threads_as_user2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For session linking
    session_id = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user1', 'user2']
        ordering = ['-updated_at']
    
    @property
    def other_user(self, current_user):
        """Get the other user in the thread"""
        if current_user == self.user1:
            return self.user2
        return self.user1


class Message(models.Model):
    """Individual chat message"""
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('system', 'System'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='sent_messages')
    
    # Message content
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    file = models.FileField(upload_to='chat_files/', null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class TypingIndicator(models.Model):
    """Track typing status in chat threads"""
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_typing = models.BooleanField(default=False)
    last_typing = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['thread', 'user']


# ========== SHARED ==========
class CommunicationSession(models.Model):
    """Link calls/chat to paid sessions"""
    thread = models.OneToOneField(ChatThread, on_delete=models.CASCADE, 
                                 related_name='communication_session', null=True, blank=True)
    call_session = models.OneToOneField(CallSession, on_delete=models.CASCADE, 
                                       related_name='communication_session', null=True, blank=True)
    
    session_id = models.CharField(max_length=255, unique=True)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='client_sessions')
    professional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                    related_name='professional_sessions')
    
    # Session details
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, null=True, blank=True)
    communication_type = models.CharField(max_length=20)  # 'chat', 'voice', 'video'
    status = models.CharField(max_length=20, default='active')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Payment
    payment_status = models.CharField(max_length=20, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration = models.IntegerField(default=0)  # in seconds
    
    class Meta:
        ordering = ['-started_at']
