from django.db import models
from django.contrib.auth import get_user_model
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()

# ============ BASE MODELS ============

class Category(models.Model):
    """Main service categories"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=20, default='#3B82F6')
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    enabled = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    avg_response_time = models.IntegerField(default=15, help_text="Average response time in minutes")
    created_at = models.DateTimeField(null=True, blank=True)  # CHANGE THIS
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def update_stats(self):
        """Update category statistics"""
        try:
            from django.db.models import Avg
            sessions = self.sessions.all()
            if sessions.exists():
                self.avg_response_time = sessions.aggregate(
                    avg=Avg('response_time')
                )['avg'] or 15
            self.save()
        except Exception as e:
            print(f"Error updating stats for {self.name}: {e}")

class SubCategory(models.Model):
    """Sub-categories under main categories"""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Sub Categories"

    def __str__(self):
        return f"{self.category.name} - {self.name}"

# ============ PROFESSIONAL MODELS ============

class Professional(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='professional_profile')
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=200, blank=True, null=True)
    specialization = models.CharField(max_length=200)
    
    # Primary category for filtering
    primary_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_professionals')

    # ✅ ADD THIS ONE LINE ONLY:
    category = property(lambda self: self.primary_category)
    
    # Bio and details
    bio = models.TextField(blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)
    languages = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    
    # Contact
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, unique=True)
    profile_picture = models.ImageField(upload_to='professionals/', blank=True, null=True)
    expo_push_token = models.CharField(max_length=255, blank=True, null=True)
    
    # Rates
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Base rate per minute
    chat_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    voice_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    video_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Video rate per minute
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    available = models.BooleanField(default=True)
    online_status = models.BooleanField(default=False)
    max_simultaneous_sessions = models.IntegerField(default=3)
    
    # Approval
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    # Verification
    license_number = models.CharField(max_length=100, blank=True, null=True)
    verified = models.BooleanField(default=False)
    
    # Video call specific
    video_call_enabled = models.BooleanField(default=True)
    max_video_duration = models.PositiveIntegerField(default=60, help_text="Maximum video call duration in minutes")
    
    # Stats (calculated)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sessions = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    avg_response_time = models.IntegerField(default=15, help_text="Average response time in seconds")
    total_calls = models.PositiveIntegerField(default=0)
    total_call_duration = models.PositiveIntegerField(default=0, help_text="Total call duration in minutes")
    average_call_duration = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage of successful sessions")
    
    # Locking for session management
    locked_by = models.CharField(max_length=100, blank=True, null=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-average_rating', '-created_at']

    def __str__(self):
        return f"{self.name} - {self.specialization}"

    def save(self, *args, **kwargs):
        # Update video rate to be 2x base rate if not set
        if self.video_rate == 0 and self.rate > 0:
            self.video_rate = self.rate * 2
        
        # Update timestamps for status changes
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
        elif self.status == 'rejected' and not self.rejected_at:
            self.rejected_at = timezone.now()
            if not self.rejection_reason:
                self.rejection_reason = "Rejected by administrator"
        
        super().save(*args, **kwargs)

    @property
    def video_rate_per_minute(self):
        """Video calls cost 2x the regular rate"""
        return self.video_rate if self.video_rate > 0 else self.rate * 2

    @property
    def video_rate_per_second(self):
        """Rate per second for real-time calculation"""
        return float(self.video_rate_per_minute) / 60

    @property
    def is_available_for_session(self):
        """Check if professional is available for new sessions"""
        if not self.available or not self.online_status:
            return False
        
        # Check if locked
        if self.locked_until and self.locked_until > timezone.now():
            return False
        
        # Check current workload
        from .models import Session
        active_sessions = Session.objects.filter(
            professional=self,
            status__in=['active', 'in_progress', 'pending']
        ).count()
        
        return active_sessions < self.max_simultaneous_sessions

    def release_lock(self):
        """Release any active lock on the professional"""
        self.locked_by = None
        self.locked_until = None
        self.save()

class ProfessionalCategory(models.Model):
    """Many-to-many relationship between professionals and categories"""
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    years_experience = models.PositiveIntegerField(default=0)
    rate_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['professional', 'category']
        verbose_name_plural = "Professional Categories"

    def __str__(self):
        return f"{self.professional.name} - {self.category.name}"

class ProfessionalSpecialization(models.Model):
    """Specific specializations within categories"""
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    #created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['professional', 'category', 'name']

    def __str__(self):
        return f"{self.professional.name} - {self.name}"

class ProfessionalAvailability(models.Model):
    DAYS_OF_WEEK = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]
    
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.CharField(max_length=20, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    #created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)  # ADD default here
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['professional', 'day_of_week']
        verbose_name_plural = "Professional Availabilities"

    def __str__(self):
        return f"{self.professional.name} - {self.get_day_of_week_display()}"

class ProfessionalDocument(models.Model):
    DOCUMENT_TYPES = [
        ('license', 'Professional License'),
        ('certificate', 'Certificate'),
        ('degree', 'Degree'),
        ('id', 'ID/Passport'),
        ('other', 'Other'),
    ]
    
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='professional_documents/')
    verified = models.BooleanField(default=False)
    #uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.professional.name} - {self.get_document_type_display()}"

# ============ CLIENT MODELS ============

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='clients/', blank=True, null=True)
    video_call_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

# ============ SESSION MODELS ============

class Session(models.Model):
    SESSION_TYPES = [
        ('audio', 'Voice Call'),
        ('video', 'Video Call'),
        ('chat', 'Chat'),
        ('in_person', 'In Person'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('disconnected', 'Disconnected'),
        ('expired', 'Expired'),
        ('declined', 'Declined'),
    ]
    
    MODE_CHOICES = [
        ('instant', 'Instant'),
        ('scheduled', 'Scheduled'),
    ]
    
    URGENCY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    CALL_QUALITY_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('failed', 'Failed'),
    ]
    
    # Basic info
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='sessions')
    client_id = models.IntegerField()  # Simple client ID (can be linked to Client model)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='audio')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Category and details
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    room_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='instant')
    
    # Timing
    scheduled_start = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(default=0, help_text="Scheduled duration in minutes")
    
    # Call details
    call_started_at = models.DateTimeField(null=True, blank=True)
    call_ended_at = models.DateTimeField(null=True, blank=True)
    call_duration = models.PositiveIntegerField(default=0, help_text="Actual call duration in seconds")
    call_quality = models.CharField(max_length=20, choices=CALL_QUALITY_CHOICES, default='good')
    call_issues = models.JSONField(default=list, blank=True)
    
    # Financials
    rate_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Ratings
    client_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    client_review = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.id}: {self.professional.name} - Client {self.client_id}"

    @property
    def total_duration(self):
        """Calculate total session duration in minutes"""
        if self.actual_start and self.ended_at:
            duration = (self.ended_at - self.actual_start).total_seconds() / 60
            return round(duration, 2)
        return 0

    @property
    def call_duration_minutes(self):
        """Get call duration in minutes"""
        return self.call_duration / 60 if self.call_duration > 0 else 0

    @property
    def has_call_issues(self):
        """Check if there were any call issues"""
        return len(self.call_issues) > 0

class SessionBooking(models.Model):
    """Bookings for scheduled sessions"""
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='booking')
    booked_by = models.CharField(max_length=255)
    scheduled_for = models.DateTimeField()
    booked_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Booking for Session {self.session.id}"

# ============ PAYMENT MODELS ============

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('wallet', 'Wallet'),
        ('cash', 'Cash'),
    ]
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='mpesa')
    transaction_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    
    # M-Pesa specific fields
    merchant_request_id = models.CharField(max_length=255, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=255, blank=True, null=True)
    response_code = models.CharField(max_length=10, blank=True, null=True)
    response_description = models.CharField(max_length=255, blank=True, null=True)
    customer_message = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    receipt_number = models.CharField(max_length=255, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} - ${self.amount}"

    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == 'completed'

class Dispute(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='disputes')
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.TextField(blank=True, null=True)
    created_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute: {self.title}"

    @property
    def time_to_resolve(self):
        """Calculate time to resolve in hours"""
        if self.resolved_at and self.created_at:
            return (self.resolved_at - self.created_at).total_seconds() / 3600
        return None

# ============ CHAT MESSAGES ============

class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('voice', 'Voice'),
        ('video', 'Video'),
        ('system', 'System'),
    ]
    
    SENDER_TYPES = [
        ('client', 'Client'),
        ('professional', 'Professional'),
        ('system', 'System'),
    ]
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='chat_messages')
    message_id = models.CharField(max_length=255, unique=True, default=uuid.uuid4)
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    message = models.TextField(blank=True, null=True)
    content = models.JSONField(default=dict, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.message_id[:8]} from {self.sender_type}"

# ============ USER PROFILE ============

class UserProfile(models.Model):
    USER_TYPES = [
        ('client', 'Client'),
        ('professional', 'Professional'),
        ('admin', 'Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='client')
    phone = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    preferences = models.JSONField(default=dict, blank=True)
    notification_preferences = models.JSONField(default=dict, blank=True)
    notification_settings = models.JSONField(default=dict, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

# ============ NOTIFICATIONS ============

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('session_request', 'Session Request'),
        ('session_accepted', 'Session Accepted'),
        ('session_rejected', 'Session Rejected'),
        ('session_reminder', 'Session Reminder'),
        ('payment_received', 'Payment Received'),
        ('payment_failed', 'Payment Failed'),
        ('rating_received', 'Rating Received'),
        ('system_alert', 'System Alert'),
        ('promotional', 'Promotional'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    read = models.BooleanField(default=False)
    related_session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True)
    action_url = models.URLField(blank=True, null=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type}: {self.title}"

# ============ CALL LOGS ============

class CallLog(models.Model):
    CALL_TYPES = [
        ('audio', 'Voice Call'),
        ('video', 'Video Call'),
    ]
    
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('in_progress', 'In Progress'),
        ('ended', 'Ended'),
        ('missed', 'Missed'),
        ('failed', 'Failed'),
    ]
    
    CALL_QUALITY_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('failed', 'Failed'),
    ]
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='call_logs')
    call_type = models.CharField(max_length=20, choices=CALL_TYPES, default='audio')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    call_quality = models.CharField(max_length=20, choices=CALL_QUALITY_CHOICES, default='good')
    connection_quality = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, help_text="0-1 scale")
    
    # Technical details
    client_device = models.CharField(max_length=255, blank=True, null=True)
    professional_device = models.CharField(max_length=255, blank=True, null=True)
    audio_issues = models.JSONField(default=list, blank=True)
    video_issues = models.JSONField(default=list, blank=True)
    network_conditions = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"Call Log: {self.session.id} - {self.call_type}"

    @property
    def duration_minutes(self):
        """Get duration in minutes"""
        return self.duration / 60 if self.duration > 0 else 0

    @property
    def has_technical_issues(self):
        """Check if there were technical issues"""
        return len(self.audio_issues) > 0 or len(self.video_issues) > 0
class CallAnalytics(models.Model):
    """Daily call analytics for professionals"""
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='call_analytics')
    date = models.DateField()
    total_calls = models.PositiveIntegerField(default=0)
    completed_calls = models.PositiveIntegerField(default=0)
    failed_calls = models.PositiveIntegerField(default=0)
    missed_calls = models.PositiveIntegerField(default=0)
    total_duration = models.PositiveIntegerField(default=0, help_text="Total duration in seconds")
    
    # FIX: Database has avg_call_duration, not average_duration
    avg_call_duration = models.FloatField(default=0.00)  # Changed from average_duration
    
    avg_quality_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    technical_issues = models.PositiveIntegerField(default=0)
    
    # FIX: Database has double precision for success_rate
    success_rate = models.FloatField(default=0.00, help_text="Percentage")
    
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    # Already fixed:
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['professional', 'date']
        verbose_name_plural = "Call Analytics"

    def __str__(self):
        return f"Analytics: {self.professional.name} - {self.date}"

    @property
    def total_duration_minutes(self):
        """Get total duration in minutes"""
        return self.total_duration / 60 if self.total_duration > 0 else 0

    @property
    def issue_rate(self):
        """Calculate issue rate percentage"""
        if self.total_calls > 0:
            return (self.technical_issues / self.total_calls) * 100
        return 0

class CallRecording(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('deleted', 'Deleted'),
    ]
    
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='recording')
    call_log = models.ForeignKey(CallLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='recordings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.PositiveBigIntegerField(default=0, help_text="Size in bytes")
    duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    storage_location = models.CharField(max_length=100, default='local')
    client_consent = models.BooleanField(default=False)
    professional_consent = models.BooleanField(default=False)
    available_for_download = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Recording: {self.session.id}"

    @property
    def duration_minutes(self):
        """Get duration in minutes"""
        return self.duration / 60 if self.duration > 0 else 0

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        return self.file_size / (1024 * 1024) if self.file_size > 0 else 0

class CallIssueReport(models.Model):
    ISSUE_TYPES = [
        ('audio', 'Audio Issues'),
        ('video', 'Video Issues'),
        ('connection', 'Connection Issues'),
        ('platform', 'Platform Issues'),
        ('other', 'Other'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='issue_reports')
    call_log = models.ForeignKey(CallLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='issue_reports')
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    description = models.TextField()
    steps_to_reproduce = models.TextField(blank=True, null=True)
    expected_behavior = models.TextField(blank=True, null=True)
    actual_behavior = models.TextField(blank=True, null=True)
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True, null=True)
    reported_by = models.CharField(max_length=255)
    resolved_by = models.CharField(max_length=255, blank=True, null=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f"Issue: {self.title}"

    @property
    def time_to_resolve(self):
        """Calculate time to resolve in hours"""
        if self.resolved_at and self.reported_at:
            return (self.resolved_at - self.reported_at).total_seconds() / 3600
        return None

# ============ FAVORITES ============

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'professional']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ❤️ {self.professional.name}"

# ============ RECEIPTS ============

class Receipt(models.Model):
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('wallet', 'Wallet'),
        ('cash', 'Cash'),
    ]
    
    SERVICE_TYPES = [
        ('audio', 'Voice Call'),
        ('video', 'Video Call'),
        ('chat', 'Chat Consultation'),
        ('in_person', 'In-Person Session'),
    ]
    
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='receipts')
    receipt_number = models.CharField(max_length=50, unique=True, default=uuid.uuid4().hex[:16].upper())
    client_name = models.CharField(max_length=255)
    professional_name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    issue_date = models.DateField(auto_now_add=True)
    issue_time = models.TimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date', '-issue_time']

    def __str__(self):
        return f"Receipt {self.receipt_number}"

# ============ SUPPORT TICKETS ============

class SupportTicket(models.Model):
    CATEGORIES = [
        ('technical', 'Technical Issues'),
        ('billing', 'Billing & Payments'),
        ('session', 'Session Issues'),
        ('account', 'Account Issues'),
        ('feedback', 'Feedback & Suggestions'),
        ('other', 'Other'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    category = models.CharField(max_length=20, choices=CATEGORIES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket: {self.subject}"

# ============ VIDEO CALL MODELS ============

class VideoSession(models.Model):
    SESSION_STATUS_CHOICES = [
        ('initializing', 'Initializing'),
        ('connecting', 'Connecting'),
        ('ringing', 'Ringing'),
        ('active', 'Active'),
        ('ending', 'Ending'),
        ('ended', 'Ended'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CALL_QUALITY_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('failed', 'Failed'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Credit/Debit Card'),
        ('wallet', 'Wallet Balance'),
        ('cash', 'Cash'),
        ('free', 'Free'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Basic Information
    id = models.CharField(max_length=50, primary_key=True, default=uuid.uuid4().hex[:20])
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='video_sessions')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='video_sessions')
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='initializing')
    
    # Room Information
    room_id = models.CharField(max_length=255, unique=True)
    room_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Timing Information
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    call_started_at = models.DateTimeField(null=True, blank=True)
    call_ended_at = models.DateTimeField(null=True, blank=True)
    call_duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    
    # Duration Limits
    max_duration = models.PositiveIntegerField(default=3600, help_text="Maximum allowed duration in seconds")
    warning_threshold = models.PositiveIntegerField(default=300, help_text="Warning before end in seconds")
    
    # Cost Calculation
    professional_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost_per_second = models.DecimalField(max_digits=10, decimal_places=6, default=0.00)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Payment Information
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='mpesa')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=255, blank=True, null=True)
    payment_confirmed = models.BooleanField(default=False)
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Technical Details
    call_quality = models.CharField(max_length=20, choices=CALL_QUALITY_CHOICES, default='good')
    network_stability = models.CharField(max_length=20, blank=True, null=True)
    platform = models.CharField(max_length=50, blank=True, null=True)
    device_info = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    # Media Settings
    client_video_enabled = models.BooleanField(default=True)
    client_audio_enabled = models.BooleanField(default=True)
    professional_video_enabled = models.BooleanField(default=True)
    professional_audio_enabled = models.BooleanField(default=True)
    recording_enabled = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True, null=True)
    
    # Call Data
    call_data = models.JSONField(default=dict, blank=True)
    error_log = models.TextField(blank=True, null=True)
    
    # Flags
    is_test_call = models.BooleanField(default=False)
    requires_followup = models.BooleanField(default=False)
    followup_scheduled = models.DateTimeField(null=True, blank=True)
    
    # Ratings
    client_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    client_feedback = models.TextField(blank=True, null=True)
    professional_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    professional_feedback = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_id']),
            models.Index(fields=['status']),
            models.Index(fields=['professional', 'status']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['call_started_at']),
        ]

    def __str__(self):
        return f"Video Session: {self.professional.name} - {self.client.name} ({self.status})"

    def save(self, *args, **kwargs):
        # Calculate cost per second based on professional's video rate
        if not self.cost_per_second and self.professional:
            self.cost_per_second = self.professional.video_rate_per_second
        
        # Update professional rate if not set
        if not self.professional_rate and self.professional:
            self.professional_rate = self.professional.rate
        
        # Calculate estimated cost
        if self.call_duration > 0 and self.cost_per_second:
            self.estimated_cost = float(self.cost_per_second) * self.call_duration
        
        super().save(*args, **kwargs)
    
    @property
    def formatted_duration(self):
        """Return duration in MM:SS format"""
        minutes = self.call_duration // 60
        seconds = self.call_duration % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def is_ended(self):
        return self.status in ['ended', 'completed', 'failed', 'cancelled']
    
    @property
    def can_be_rated(self):
        return self.status == 'ended' and self.client_rating is None
    
    def start_call(self):
        """Mark call as started"""
        self.status = 'active'
        self.call_started_at = timezone.now()
        self.save()
    
    def end_call(self, duration=None, quality='good'):
        """Mark call as ended"""
        self.status = 'ended'
        self.call_ended_at = timezone.now()
        
        if duration:
            self.call_duration = duration
        elif self.call_started_at:
            self.call_duration = (self.call_ended_at - self.call_started_at).total_seconds()
        
        self.call_quality = quality
        
        # Calculate actual cost
        if self.call_duration > 0 and self.cost_per_second:
            self.actual_cost = float(self.cost_per_second) * self.call_duration
        
        self.save()

class VideoCallLog(models.Model):
    """Detailed log for video call events"""
    EVENT_TYPE_CHOICES = [
        ('call_initiated', 'Call Initiated'),
        ('call_answered', 'Call Answered'),
        ('call_ended', 'Call Ended'),
        ('call_failed', 'Call Failed'),
        ('quality_change', 'Quality Change'),
        ('mute_toggle', 'Mute Toggle'),
        ('video_toggle', 'Video Toggle'),
        ('camera_switch', 'Camera Switch'),
        ('network_change', 'Network Change'),
        ('payment_processed', 'Payment Processed'),
        ('rating_submitted', 'Rating Submitted'),
    ]
    
    session = models.ForeignKey(VideoSession, on_delete=models.CASCADE, related_name='call_logs')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    event_data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.timestamp}"

class VideoCallPayment(models.Model):
    """Detailed payment information for video calls"""
    session = models.OneToOneField(VideoSession, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    transaction_id = models.CharField(max_length=255, unique=True)
    payment_gateway = models.CharField(max_length=50, default='mpesa')
    gateway_response = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=VideoSession.PAYMENT_STATUS_CHOICES, default='pending')
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    receipt_url = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ['-initiated_at']

    def __str__(self):
        return f"Payment: {self.amount} {self.currency} - {self.status}"

class VideoCallRecording(models.Model):
    """Recordings of video calls"""
    session = models.OneToOneField(VideoSession, on_delete=models.CASCADE, related_name='recording')
    recording_id = models.CharField(max_length=255, unique=True)
    storage_url = models.URLField()
    storage_path = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField(help_text="Size in bytes")
    duration = models.PositiveIntegerField(help_text="Duration in seconds")
    format = models.CharField(max_length=20, default='mp4')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Recording: {self.session.room_id} ({self.duration}s)"


# ADDED TO HANDLE PROFESSIONAL REFGISTRATION ON 9TH DEC 2025
# Add these imports at the top
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import uuid

# ============ SIGNALS ============

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)
        
@receiver(post_save, sender=UserProfile)
def create_professional_or_client_profile(sender, instance, created, **kwargs):
    """Create Professional or Client profile when UserProfile is created/updated"""
    
    # Create Professional if user_type is 'professional'
    if instance.user_type == 'professional':
        # Check if Professional already exists
        professional_exists = Professional.objects.filter(user=instance.user).exists()
        
        if not professional_exists:
            try:
                # Create Professional profile with default values
                professional = Professional.objects.create(
                    user=instance.user,
                    name=instance.user.get_full_name() or instance.user.username,
                    email=instance.user.email,
                    phone=instance.phone or '',
                    specialization='General',
                    license_number='Pending',
                    status='pending',
                    rate=50.00,
                    chat_rate=25.00,
                    voice_rate=30.00,
                    video_rate=100.00,
                    video_call_enabled=True,
                    available=True,
                    online_status=False
                )
                print(f"✅ Created Professional profile for {instance.user.username}")
                
            except Exception as e:
                print(f"❌ Error creating Professional profile: {e}")
    
    # Create Client if user_type is 'client'  
    elif instance.user_type == 'client':
        # Check if Client already exists
        client_exists = Client.objects.filter(user=instance.user).exists()
        
        if not client_exists:
            try:
                Client.objects.create(
                    user=instance.user,
                    name=instance.user.get_full_name() or instance.user.username,
                    phone=instance.phone or '',
                    video_call_balance=0.00
                )
                print(f"✅ Created Client profile for {instance.user.username}")
            except Exception as e:
                print(f"❌ Error creating Client profile: {e}")

@receiver(post_save, sender=UserProfile)
def save_professional_or_client_profile(sender, instance, **kwargs):
    """Update Professional or Client when UserProfile is updated"""
    try:
        if instance.user_type == 'professional' and hasattr(instance.user, 'professional_profile'):
            # Update Professional with UserProfile data
            professional = instance.user.professional_profile
            professional.name = instance.user.get_full_name() or instance.user.username
            professional.email = instance.user.email
            professional.phone = instance.phone or ''
            professional.save()
            
        elif instance.user_type == 'client' and hasattr(instance.user, 'client_profile'):
            # Update Client with UserProfile data
            client = instance.user.client_profile
            client.name = instance.user.get_full_name() or instance.user.username
            client.phone = instance.phone or ''
            client.save()
            
    except Exception as e:
        print(f"❌ Error updating profile: {e}")
