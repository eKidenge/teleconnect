from rest_framework import serializers
from .models import (
    Professional, Session, Payment, Dispute, ChatMessage, 
    UserProfile, Category, Favorite, Notification, ProfessionalCategory,
    ProfessionalAvailability, ProfessionalDocument, CallLog, CallAnalytics,
    CallRecording, CallIssueReport, SessionBooking, ProfessionalSpecialization,
    Receipt, SupportTicket, SubCategory
)

class ProfessionalSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='primary_category.name', read_only=True)
    is_online = serializers.BooleanField(source='online_status', read_only=True)
    is_available = serializers.BooleanField(source='available', read_only=True)
    application_status = serializers.CharField(source='status', read_only=True)
    is_approved = serializers.BooleanField(source='is_approved', read_only=True)
    
    class Meta:
        model = Professional
        fields = [
            'id', 'name', 'email', 'specialization', 'rate', 
            'category_name', 'is_online', 'is_available', 
            'application_status', 'is_approved', 'average_rating', 
            'total_sessions', 'experience_years', 'bio', 'phone', 
            'created_at', 'approved_at', 'rejection_reason', 'rejected_at',
            'title', 'profile_picture', 'languages', 'education', 'certifications',
            'success_rate', 'current_workload', 'max_workload', 'last_active',
            'total_calls', 'total_call_duration', 'avg_response_time'
        ]

class SessionSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    professional_specialization = serializers.CharField(source='professional.specialization', read_only=True)
    professional_rate = serializers.DecimalField(source='professional.rate', max_digits=6, decimal_places=2, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Session
        fields = [
            'id', 'professional', 'professional_name', 'professional_specialization',
            'professional_rate', 'client_id', 'session_type', 'status', 'category',
            'category_name', 'scheduled_start', 'actual_start', 'ended_at', 'duration',
            'cost', 'rate_used', 'rating', 'review', 'room_id', 'call_started_at',
            'call_ended_at', 'call_duration', 'call_quality', 'call_issues', 'urgency',
            'mode', 'created_at', 'updated_at'
        ]

class PaymentSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    professional_name = serializers.CharField(source='session.professional.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'session', 'session_info', 'professional_name', 'amount', 'status',
            'payment_method', 'transaction_id', 'checkout_request_id', 'phone_number',
            'receipt_number', 'created_at', 'completed_at'
        ]

class DisputeSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    professional_name = serializers.CharField(source='session.professional.name', read_only=True)
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'session', 'session_info', 'professional_name', 'title', 'description',
            'status', 'created_by', 'created_at', 'resolved_at', 'resolution'
        ]

class ChatMessageSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    sender_name = serializers.CharField(source='get_sender_type_display', read_only=True)
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'session', 'session_info', 'message_id', 'message', 'sender_type',
            'sender_name', 'message_type', 'created_at', 'read', 'content'
        ]

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'username', 'email', 'first_name', 'last_name', 'user_type',
            'phone', 'date_of_birth', 'avatar', 'favorite_professionals', 'location',
            'timezone', 'notification_preferences', 'preferences', 'notification_settings',
            'is_verified', 'created_at', 'updated_at'
        ]

class CategorySerializer(serializers.ModelSerializer):
    professional_count = serializers.IntegerField(read_only=True)
    session_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'base_price', 'enabled', 'professional_count',
            'session_count', 'icon', 'color', 'avg_response_time', 'is_featured',
            'sort_order', 'created_at', 'updated_at'
        ]

class FavoriteSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    professional_specialization = serializers.CharField(source='professional.specialization', read_only=True)
    professional_rate = serializers.DecimalField(source='professional.rate', max_digits=6, decimal_places=2, read_only=True)
    
    class Meta:
        model = Favorite
        fields = [
            'id', 'user', 'professional', 'professional_name', 'professional_specialization',
            'professional_rate', 'created_at'
        ]

class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'notification_type', 'title', 'message', 'read',
            'related_session', 'data', 'priority', 'action_url', 'created_at'
        ]

class ProfessionalCategorySerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = ProfessionalCategory
        fields = [
            'id', 'professional', 'professional_name', 'category', 'category_name',
            'is_primary', 'years_experience', 'certification', 'verified',
            'rate_override', 'created_at'
        ]

class ProfessionalAvailabilitySerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = ProfessionalAvailability
        fields = [
            'id', 'professional', 'professional_name', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'is_available'
        ]

class ProfessionalDocumentSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    document_type_name = serializers.CharField(source='get_document_type_display', read_only=True)
    
    class Meta:
        model = ProfessionalDocument
        fields = [
            'id', 'professional', 'professional_name', 'document_type', 'document_type_name',
            'file', 'verified', 'uploaded_at'
        ]

class CallLogSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    professional_name = serializers.CharField(source='session.professional.name', read_only=True)
    
    class Meta:
        model = CallLog
        fields = [
            'id', 'session', 'session_info', 'professional_name', 'call_type', 'status',
            'start_time', 'end_time', 'duration', 'call_quality', 'connection_quality',
            'audio_issues', 'video_issues', 'client_device', 'professional_device',
            'network_conditions', 'created_at'
        ]

class CallAnalyticsSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    
    class Meta:
        model = CallAnalytics
        fields = [
            'id', 'professional', 'professional_name', 'date', 'total_calls',
            'completed_calls', 'failed_calls', 'missed_calls', 'total_duration',
            'average_duration', 'average_quality_score', 'calls_with_issues',
            'success_rate', 'average_rating', 'created_at', 'updated_at'
        ]

class CallRecordingSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    professional_name = serializers.CharField(source='session.professional.name', read_only=True)
    
    class Meta:
        model = CallRecording
        fields = [
            'id', 'session', 'session_info', 'professional_name', 'call_log',
            'file_path', 'file_size', 'duration', 'status', 'storage_location',
            'client_consent', 'professional_consent', 'available_for_download',
            'created_at', 'processed_at'
        ]

class CallIssueReportSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    professional_name = serializers.CharField(source='session.professional.name', read_only=True)
    
    class Meta:
        model = CallIssueReport
        fields = [
            'id', 'session', 'session_info', 'professional_name', 'call_log',
            'issue_type', 'priority', 'title', 'description', 'steps_to_reproduce',
            'expected_behavior', 'actual_behavior', 'reported_by', 'reported_at',
            'resolved', 'resolution_notes', 'resolved_by', 'resolved_at'
        ]

class SessionBookingSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    professional_name = serializers.CharField(source='session.professional.name', read_only=True)
    
    class Meta:
        model = SessionBooking
        fields = [
            'id', 'session', 'session_info', 'professional_name', 'booked_by',
            'booked_at', 'scheduled_for', 'notes'
        ]

class ProfessionalSpecializationSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = ProfessionalSpecialization
        fields = [
            'id', 'professional', 'professional_name', 'category', 'category_name',
            'name', 'description'
        ]

class ReceiptSerializer(serializers.ModelSerializer):
    session_info = serializers.CharField(source='session.id', read_only=True)
    payment_info = serializers.CharField(source='payment.id', read_only=True)
    
    class Meta:
        model = Receipt
        fields = [
            'id', 'receipt_number', 'payment', 'payment_info', 'session', 'session_info',
            'client_name', 'professional_name', 'service_type', 'amount', 'transaction_id',
            'payment_method', 'issue_date', 'issue_time', 'created_at'
        ]

class SupportTicketSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'user', 'user_name', 'user_email', 'subject', 'message', 'category',
            'priority', 'status', 'related_session', 'related_payment', 'created_at',
            'updated_at', 'resolved_at'
        ]

class SubCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = SubCategory
        fields = [
            'id', 'category', 'category_name', 'name', 'description', 'enabled',
            'created_at'
        ]

# Simplified serializers for specific use cases
class ProfessionalListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='primary_category.name', read_only=True)
    is_approved = serializers.BooleanField(source='is_approved', read_only=True)
    
    class Meta:
        model = Professional
        fields = [
            'id', 'name', 'specialization', 'rate', 'available', 'online_status',
            'category_name', 'average_rating', 'total_sessions', 'experience_years',
            'is_approved', 'avg_response_time'
        ]

class SessionListSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.name', read_only=True)
    professional_specialization = serializers.CharField(source='professional.specialization', read_only=True)
    
    class Meta:
        model = Session
        fields = [
            'id', 'professional_name', 'professional_specialization', 'session_type',
            'status', 'duration', 'cost', 'created_at', 'ended_at', 'client_id'
        ]

class UserProfileBasicSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'username', 'email', 'user_type', 'phone', 'location',
            'is_verified', 'created_at'
        ]

# Analytics serializers
class AnalyticsSummarySerializer(serializers.Serializer):
    total_professionals = serializers.IntegerField()
    pending_approvals = serializers.IntegerField()
    approved_professionals = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    active_disputes = serializers.IntegerField()
    monthly_growth = serializers.DecimalField(max_digits=5, decimal_places=2)
    completed_sessions = serializers.IntegerField()
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()

class RevenueChartSerializer(serializers.Serializer):
    labels = serializers.ListField(child=serializers.CharField())
    data = serializers.ListField(child=serializers.DecimalField(max_digits=10, decimal_places=2))

class RecentActivitySerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    message = serializers.CharField()
    timestamp = serializers.DateTimeField()

# Matching algorithm serializers
class MatchingPreferencesSerializer(serializers.Serializer):
    max_rate = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    min_rating = serializers.DecimalField(max_digits=3, decimal_places=2, required=False)
    max_response_time = serializers.CharField(required=False)
    min_experience = serializers.IntegerField(required=False)
    required_specializations = serializers.ListField(child=serializers.CharField(), required=False)

class MatchingResultSerializer(serializers.Serializer):
    professional = ProfessionalListSerializer()
    matching_score = serializers.DecimalField(max_digits=5, decimal_places=3)
    score_breakdown = serializers.DictField()
    recommendation_reason = serializers.CharField()

# Payment serializers
class MpesaPaymentSerializer(serializers.Serializer):
    phoneNumber = serializers.CharField()
    amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    professionalId = serializers.IntegerField()
    sessionId = serializers.IntegerField(required=False)

class CardPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    session_id = serializers.IntegerField()
    card_details = serializers.DictField()

class BankTransferSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    session_id = serializers.IntegerField()
    bank_details = serializers.DictField()

# Notification serializers
class NotificationCreateSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    title = serializers.CharField()
    message = serializers.CharField()
    type = serializers.CharField(required=False)
    data = serializers.DictField(required=False)

# Support serializers
class SupportTicketCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    subject = serializers.CharField()
    message = serializers.CharField()
    category = serializers.CharField(required=False)
    priority = serializers.CharField(required=False)

class ContactSupportSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField()
    subject = serializers.CharField()
    message = serializers.CharField()
    category = serializers.CharField(required=False)
    user_id = serializers.IntegerField(required=False)
