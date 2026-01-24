from django.db import models
from django.conf import settings
#from sessions.models import Session  # Assuming you have Session model

class WebRTCCall(models.Model):
    CALL_STATUS = [
        ('pending', 'Pending'),
        ('ringing', 'Ringing'),
        ('connecting', 'Connecting'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('failed', 'Failed'),
        ('missed', 'Missed'),
        ('declined', 'Declined'),
    ]
    
    CALL_TYPE = [
        ('audio', 'Audio Call'),
        ('video', 'Video Call'),
    ]
    
    #session = models.OneToOneField('sessions.Session', on_delete=models.CASCADE, related_name='webrtc_call')
    call_type = models.CharField(max_length=10, choices=CALL_TYPE, default='audio')
    status = models.CharField(max_length=20, choices=CALL_STATUS, default='pending')
    room_id = models.CharField(max_length=255, unique=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(default=0)  # in seconds
    call_quality = models.CharField(max_length=20, default='good')
    connection_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.call_type} call for Session {self.session.id} - {self.status}"

class ICEConnection(models.Model):
    call = models.ForeignKey(WebRTCCall, on_delete=models.CASCADE, related_name='ice_connections')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    candidate = models.TextField()
    sdp_mid = models.CharField(max_length=255, null=True, blank=True)
    sdp_mline_index = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']

class CallSignal(models.Model):
    SIGNAL_TYPES = [
        ('offer', 'Offer'),
        ('answer', 'Answer'),
        ('candidate', 'ICE Candidate'),
        ('hangup', 'Hang Up'),
        ('ringing', 'Ringing'),
        ('connected', 'Connected'),
    ]
    
    call = models.ForeignKey(WebRTCCall, on_delete=models.CASCADE, related_name='signals')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_signals')
    signal_type = models.CharField(max_length=20, choices=SIGNAL_TYPES)
    signal_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.signal_type} from {self.sender}"

class PeerConnection(models.Model):
    CONNECTION_STATES = [
        ('new', 'New'),
        ('connecting', 'Connecting'),
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('failed', 'Failed'),
        ('closed', 'Closed'),
    ]
    
    call = models.ForeignKey(WebRTCCall, on_delete=models.CASCADE, related_name='peer_connections')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    connection_id = models.CharField(max_length=255)
    state = models.CharField(max_length=20, choices=CONNECTION_STATES, default='new')
    local_sdp = models.TextField(null=True, blank=True)
    remote_sdp = models.TextField(null=True, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['call', 'user']
    
    def __str__(self):
        return f"{self.user} - {self.state}"