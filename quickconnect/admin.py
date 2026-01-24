from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from django.core.exceptions import ObjectDoesNotExist
import logging
from .models import *
from django.urls import reverse
from django.shortcuts import redirect, render
from django.db import transaction

# Get logger for debugging
logger = logging.getLogger(__name__)

# ============ INLINE ADMIN CLASSES ============

class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1
    fields = ['name', 'description', 'enabled', 'created_at']
    readonly_fields = ['created_at']
    classes = ['collapse']

class ProfessionalCategoryInline(admin.TabularInline):
    model = ProfessionalCategory
    extra = 1
    fields = ['category', 'is_primary', 'years_experience', 'rate_override', 'verified']
    autocomplete_fields = ['category']
    classes = ['collapse']

class ProfessionalSpecializationInline(admin.TabularInline):
    model = ProfessionalSpecialization
    extra = 1
    fields = ['category', 'name', 'description']
    autocomplete_fields = ['category']
    classes = ['collapse']

class ProfessionalAvailabilityInline(admin.TabularInline):
    model = ProfessionalAvailability
    extra = 1
    fields = ['day_of_week', 'start_time', 'end_time', 'is_available']
    max_num = 7
    classes = ['collapse']

class ProfessionalDocumentInline(admin.TabularInline):
    model = ProfessionalDocument
    extra = 1
    fields = ['document_type', 'file', 'verified']
    #readonly_fields = ['uploaded_at']
    classes = ['collapse']

class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ['client_id', 'session_type', 'status', 'created_at']
    readonly_fields = ['created_at']
    show_change_link = True
    classes = ['collapse']
    max_num = 5

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ['sender_type', 'message_type', 'message_preview', 'created_at', 'read']
    readonly_fields = ['created_at', 'message_preview']
    max_num = 5
    classes = ['collapse']

    def message_preview(self, obj):
        return obj.message[:50] + '...' if obj.message and len(obj.message) > 50 else (obj.message or 'No message')
    message_preview.short_description = "Message"

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ['amount', 'status', 'payment_method', 'created_at']
    readonly_fields = ['created_at']
    max_num = 1
    classes = ['collapse']

class CallLogInline(admin.TabularInline):
    model = CallLog
    extra = 0
    fields = ['call_type', 'status', 'start_time', 'duration', 'call_quality']
    readonly_fields = ['start_time']
    max_num = 3
    classes = ['collapse']

class CallIssueReportInline(admin.TabularInline):
    model = CallIssueReport
    extra = 0
    fields = ['issue_type', 'priority', 'title', 'resolved']
    max_num = 2
    classes = ['collapse']

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    classes = ['collapse']

# Video Call Inlines
class VideoCallLogInline(admin.TabularInline):
    model = VideoCallLog
    extra = 0
    readonly_fields = ['event_type', 'event_data', 'timestamp', 'created_by']
    can_delete = False
    max_num = 10
    classes = ['collapse']

class VideoCallPaymentInline(admin.StackedInline):
    model = VideoCallPayment
    extra = 0
    readonly_fields = ['amount', 'currency', 'transaction_id', 'payment_gateway', 'status', 'initiated_at']
    can_delete = False
    max_num = 1
    classes = ['collapse']

# ============ MODEL ADMIN CLASSES ============

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'icon', 'base_price', 'get_professional_count', 
        'get_session_count', 'avg_response_time', 'is_featured', 
        'enabled', 'sort_order', 'created_at'
    ]
    list_filter = [
        'enabled', 'is_featured', 'created_at', 'updated_at'
    ]
    search_fields = ['name', 'description']
    list_editable = ['sort_order', 'is_featured', 'enabled', 'base_price']
    readonly_fields = [
        'get_professional_count', 'get_session_count', 'created_at', 
        'updated_at', 'stats_preview', 'professionals_list', 'link_professionals_button'
    ]
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'name', 'description', 'base_price', 'enabled'
            ]
        }),
        ('UI & Display', {
            'fields': [
                'icon', 'color', 'sort_order', 'is_featured'
            ]
        }),
        ('Statistics', {
            'fields': [
                'get_professional_count', 'get_session_count', 
                'avg_response_time', 'stats_preview'
            ]
        }),
        ('Professional Management', {
            'fields': [
                'link_professionals_button', 'professionals_list'
            ],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': [
                'created_at', 'updated_at'
            ],
            'classes': ['collapse']
        })
    ]
    inlines = [SubCategoryInline]
    actions = ['update_statistics', 'enable_categories', 'disable_categories', 
               'feature_categories', 'view_professionals_action', 'create_missing_links']
    
    def get_professional_count(self, obj):
        try:
            return obj.primary_professionals.count()
        except Exception as e:
            logger.error(f"Error getting professional count for category {obj.id}: {e}")
            return 0
    get_professional_count.short_description = "Professionals"

    def get_session_count(self, obj):
        try:
            return obj.sessions.count()
        except Exception as e:
            logger.error(f"Error getting session count for category {obj.id}: {e}")
            return 0
    get_session_count.short_description = "Sessions"

    def stats_preview(self, obj):
        try:
            linked_count = obj.professionalcategory_set.count()
            potential_count = Professional.objects.filter(primary_category=obj).count()
            
            if linked_count == 0 and potential_count > 0:
                return format_html(
                    "<b>Professionals:</b> <span style='color: orange;'>0 linked ({} available)</span> | <b>Sessions:</b> {} | <b>Avg Response:</b> {} min",
                    potential_count,
                    self.get_session_count(obj), 
                    obj.avg_response_time
                )
            else:
                return format_html(
                    "<b>Professionals:</b> {} | <b>Sessions:</b> {} | <b>Avg Response:</b> {} min",
                    linked_count, 
                    self.get_session_count(obj), 
                    obj.avg_response_time
                )
        except Exception as e:
            logger.error(f"Error in stats_preview for category {obj.id}: {e}")
            return "Error loading statistics"
    stats_preview.short_description = "Current Statistics"

    def professionals_list(self, obj):
        """Display linked professionals in the category detail page"""
        try:
            professional_categories = obj.professionalcategory_set.all()
            
            if professional_categories.exists():
                html = "<ul style='margin-left: 20px;'>"
                for pc in professional_categories:
                    html += f"<li style='margin-bottom: 5px;'>"
                    html += f"<b>{pc.professional.name}</b>"
                    if pc.is_primary:
                        html += f" <span style='background: #4CAF50; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;'>Primary</span>"
                    html += f"<br>"
                    html += f"<small>Rate: ${pc.rate_override or 'Using default'} | Experience: {pc.years_experience or 0} years</small>"
                    html += f"</li>"
                html += "</ul>"
                return format_html(html)
            else:
                professionals = Professional.objects.filter(primary_category=obj)
                if professionals.exists():
                    html = "<div style='padding: 15px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px;'>"
                    html += "<p style='color: #856404; margin-bottom: 10px;'><strong>⚠️ Professionals are NOT linked yet!</strong></p>"
                    html += "<p style='color: #856404;'>These professionals have this as their primary_category but need to be linked through ProfessionalCategory:</p>"
                    html += "<ul style='margin-left: 20px;'>"
                    for prof in professionals:
                        html += f"<li style='margin-bottom: 5px;'>"
                        html += f"<b>{prof.name}</b>"
                        html += f"<br>"
                        html += f"<small>Status: {prof.get_status_display()} | Rate: ${prof.rate or 0}</small>"
                        html += f"</li>"
                    html += "</ul>"
                    html += "</div>"
                    return format_html(html)
                else:
                    return "No professionals linked to this category"
        except Exception as e:
            logger.error(f"Error in professionals_list for category {obj.id}: {e}")
            return "Error loading professionals"
    professionals_list.short_description = "Linked Professionals"

    def link_professionals_button(self, obj):
        """Button to create missing ProfessionalCategory links"""
        try:
            professionals = Professional.objects.filter(primary_category=obj)
            linked_count = obj.professionalcategory_set.count()
            unlinked_count = professionals.count() - linked_count
            
            if unlinked_count > 0:
                url = reverse('admin:quickconnect_category_link_professionals', args=[obj.id])
                return format_html(
                    '<a href="{}" class="button" style="background: #28a745; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px;">'
                    '🔗 Link {} Professionals Now</a>',
                    url, unlinked_count
                )
            elif professionals.count() > 0:
                return format_html(
                    '<span style="color: green; padding: 5px 10px; background: #d4edda; border-radius: 4px;">'
                    '✓ All professionals are linked</span>'
                )
            else:
                return "No professionals to link"
        except Exception as e:
            logger.error(f"Error in link_professionals_button for category {obj.id}: {e}")
            return "Error"
    link_professionals_button.short_description = "Link Actions"
    link_professionals_button.allow_tags = True

    def view_professionals_action(self, request, queryset):
        """Custom action to redirect to professionals filtered by category"""
        if queryset.count() == 1:
            category = queryset.first()
            url = reverse('admin:quickconnect_professional_changelist')
            url += f'?primary_category__id__exact={category.id}'
            return redirect(url)
        else:
            self.message_user(
                request, 
                "Please select only one category to view its professionals.", 
                level='warning'
            )
    view_professionals_action.short_description = "View professionals in this category"

    def create_missing_links(self, request, queryset):
        """Create ProfessionalCategory links for professionals with primary_category"""
        total_created = 0
        
        with transaction.atomic():
            for category in queryset:
                professionals = Professional.objects.filter(primary_category=category)
                
                for prof in professionals:
                    exists = ProfessionalCategory.objects.filter(
                        professional=prof,
                        category=category
                    ).exists()
                    
                    if not exists:
                        ProfessionalCategory.objects.create(
                            professional=prof,
                            category=category,
                            is_primary=True,
                            years_experience=prof.experience_years or 0,
                            rate_override=None
                        )
                        total_created += 1
        
        if total_created > 0:
            self.message_user(
                request, 
                f"Successfully created {total_created} ProfessionalCategory links for selected categories.",
                level='success'
            )
        else:
            self.message_user(
                request,
                "No new links created. All professionals already have ProfessionalCategory links.",
                level='info'
            )
    create_missing_links.short_description = "Create missing professional links"

    def update_statistics(self, request, queryset):
        try:
            for category in queryset:
                category.update_stats()
            self.message_user(request, f"Updated statistics for {queryset.count()} categories.")
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
            self.message_user(request, f"Error updating statistics: {e}", level='error')
    update_statistics.short_description = "Update selected categories statistics"

    def enable_categories(self, request, queryset):
        updated = queryset.update(enabled=True)
        self.message_user(request, f"Enabled {updated} categories.")
    enable_categories.short_description = "Enable selected categories"

    def disable_categories(self, request, queryset):
        updated = queryset.update(enabled=False)
        self.message_user(request, f"Disabled {updated} categories.")
    disable_categories.short_description = "Disable selected categories"

    def feature_categories(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"Featured {updated} categories.")
    feature_categories.short_description = "Feature selected categories"

    def get_urls(self):
        """Add custom URL for linking professionals"""
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/link-professionals/',
                self.admin_site.admin_view(self.link_professionals_view),
                name='quickconnect_category_link_professionals'
            ),
        ]
        return custom_urls + urls
    
    def link_professionals_view(self, request, object_id):
        """View to create ProfessionalCategory links"""
        try:
            category = Category.objects.get(id=object_id)
            
            if request.method == 'POST':
                with transaction.atomic():
                    created_count = 0
                    professionals = Professional.objects.filter(primary_category=category)
                    
                    for prof in professionals:
                        exists = ProfessionalCategory.objects.filter(
                            professional=prof,
                            category=category
                        ).exists()
                        
                        if not exists:
                            ProfessionalCategory.objects.create(
                                professional=prof,
                                category=category,
                                is_primary=True,
                                years_experience=prof.experience_years or 0,
                                rate_override=None
                            )
                            created_count += 1
                
                self.message_user(
                    request, 
                    f"Successfully created {created_count} ProfessionalCategory links for {category.name}",
                    level='success'
                )
                return redirect('admin:quickconnect_category_change', object_id)
            
            professionals = Professional.objects.filter(primary_category=category)
            linked_count = category.professionalcategory_set.count()
            unlinked_count = professionals.count() - linked_count
            
            context = {
                **self.admin_site.each_context(request),
                'title': f'Link Professionals to {category.name}',
                'category': category,
                'professionals': professionals,
                'linked_count': linked_count,
                'unlinked_count': unlinked_count,
                'opts': self.model._meta,
            }
            
            return render(request, 'admin/quickconnect/link_professionals.html', context)
            
        except Category.DoesNotExist:
            self.message_user(request, "Category not found", level='error')
            return redirect('admin:quickconnect_category_changelist')

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'enabled', 'created_at']
    list_filter = ['category', 'enabled', 'created_at']
    search_fields = ['name', 'description', 'category__name']
    list_select_related = ['category']
    autocomplete_fields = ['category']
    readonly_fields = ['created_at']

@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'primary_category', 'status', 'online_status', 
        'available', 'average_rating', 'total_sessions', 
        'rate', 'created_at', 'status_badge', 'video_call_enabled'
    ]
    list_filter = [
        'status', 'available', 'online_status', 'primary_category',
        'created_at', 'approved_at', 'video_call_enabled'
    ]
    search_fields = [
        'name', 'specialization', 'email', 'phone', 
        'primary_category__name', 'title'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'approved_at', 'rejected_at',
        'stats_summary', 'availability_status', 'current_workload_display',
        'average_call_duration_display', 'video_rate_per_minute_display'
    ]
    list_editable = ['status', 'available', 'online_status', 'video_call_enabled']
    
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'user', 'name', 'title', 'specialization',
                'primary_category', 'profile_picture'
            ]
        }),
        ('Contact Information', {
            'fields': [
                'email', 'phone', 'expo_push_token'
            ]
        }),
        ('Professional Details', {
            'fields': [
                'bio', 'experience_years', 'languages',
                'education', 'certifications'
            ]
        }),
        ('Rates & Pricing', {
            'fields': [
                'rate', 'chat_rate', 'voice_rate', 'video_rate',
                'video_rate_per_minute_display', 'video_call_enabled',
                'max_video_duration'
            ]
        }),
        ('Availability & Status', {
            'fields': [
                'status', 'available', 'online_status', 
                'max_simultaneous_sessions', 'availability_status',
                'current_workload_display', 'locked_by', 'locked_until'
            ]
        }),
        ('Statistics', {
            'fields': [
                'average_rating', 'total_sessions', 'total_reviews',
                'avg_response_time', 'total_calls', 'total_call_duration',
                'average_call_duration_display', 'success_rate', 'stats_summary'
            ]
        }),
        ('Approval Information', {
            'fields': [
                'approved_at', 'rejection_reason', 'rejected_at'
            ],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': [
                'created_at', 'updated_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    #filter_horizontal = ('categories',)  # This works because 'categories' is a ManyToManyField through ProfessionalCategory
    
    inlines = [
        ProfessionalCategoryInline,
        ProfessionalSpecializationInline,
        ProfessionalAvailabilityInline,
        ProfessionalDocumentInline,
        SessionInline
    ]
    
    actions = [
        'approve_professionals', 'reject_professionals', 
        'suspend_professionals', 'update_online_status', 'release_locks',
        'update_offline_status', 'enable_video_calls', 'disable_video_calls'
    ]

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'suspended': 'gray'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = "Status"

    def video_rate_per_minute_display(self, obj):
        return f"${obj.video_rate_per_minute:.2f}/min"
    video_rate_per_minute_display.short_description = "Video Rate"

    def stats_summary(self, obj):
        try:
            return format_html(
                "<b>Rating:</b> {} ⭐ | <b>Sessions:</b> {} | <b>Success Rate:</b> {}% | <b>Response Time:</b> {}",
                obj.average_rating or 0, 
                obj.total_sessions or 0, 
                obj.success_rate or 0, 
                obj.avg_response_time or 'N/A'
            )
        except Exception as e:
            logger.error(f"Error in stats_summary for professional {obj.id}: {e}")
            return "Error loading statistics"
    stats_summary.short_description = "Performance Summary"

    def availability_status(self, obj):
        try:
            if obj.is_available_for_session:
                return format_html('<span style="color: green;">● Available for New Sessions</span>')
            else:
                return format_html('<span style="color: red;">● Not Available</span>')
        except Exception as e:
            logger.error(f"Error in availability_status for professional {obj.id}: {e}")
            return format_html('<span style="color: gray;">● Status Unknown</span>')
    availability_status.short_description = "Current Availability"

    def current_workload_display(self, obj):
        try:
            active_sessions = obj.sessions.filter(
                status__in=['active', 'in_progress', 'pending']
            ).count()
            return f"{active_sessions}/{obj.max_simultaneous_sessions}"
        except Exception as e:
            logger.error(f"Error in current_workload_display for professional {obj.id}: {e}")
            return "Error"
    current_workload_display.short_description = "Current Workload"

    def average_call_duration_display(self, obj):
        try:
            return f"{obj.average_call_duration} min"
        except Exception as e:
            logger.error(f"Error in average_call_duration_display for professional {obj.id}: {e}")
            return "Error"
    average_call_duration_display.short_description = "Avg Call Duration"

    def approve_professionals(self, request, queryset):
        updated = queryset.update(
            status='approved', 
            approved_at=timezone.now(),
            rejection_reason=''
        )
        self.message_user(request, f"Approved {updated} professionals.")
    approve_professionals.short_description = "Approve selected professionals"

    def reject_professionals(self, request, queryset):
        updated = queryset.update(
            status='rejected',
            rejected_at=timezone.now()
        )
        self.message_user(request, f"Rejected {updated} professionals.")
    reject_professionals.short_description = "Reject selected professionals"

    def suspend_professionals(self, request, queryset):
        updated = queryset.update(status='suspended')
        self.message_user(request, f"Suspended {updated} professionals.")
    suspend_professionals.short_description = "Suspend selected professionals"

    def update_online_status(self, request, queryset):
        updated = queryset.update(online_status=True)
        self.message_user(request, f"Set {updated} professionals to online.")
    update_online_status.short_description = "Set selected professionals online"

    def update_offline_status(self, request, queryset):
        updated = queryset.update(online_status=False)
        self.message_user(request, f"Set {updated} professionals to offline.")
    update_offline_status.short_description = "Set selected professionals offline"

    def enable_video_calls(self, request, queryset):
        updated = queryset.update(video_call_enabled=True)
        self.message_user(request, f"Enabled video calls for {updated} professionals.")
    enable_video_calls.short_description = "Enable video calls"

    def disable_video_calls(self, request, queryset):
        updated = queryset.update(video_call_enabled=False)
        self.message_user(request, f"Disabled video calls for {updated} professionals.")
    disable_video_calls.short_description = "Disable video calls"

    def release_locks(self, request, queryset):
        for professional in queryset:
            professional.release_lock()
        self.message_user(request, f"Released locks for {queryset.count()} professionals.")
    release_locks.short_description = "Release locks for selected professionals"

@admin.register(ProfessionalCategory)
class ProfessionalCategoryAdmin(admin.ModelAdmin):
    list_display = ['professional', 'category', 'is_primary', 'years_experience', 'verified', 'rate_override']
    list_filter = ['is_primary', 'verified', 'category']
    search_fields = ['professional__name', 'category__name']
    autocomplete_fields = ['professional', 'category']
    list_editable = ['is_primary', 'verified', 'years_experience', 'rate_override']
    readonly_fields = ['created_at']

@admin.register(ProfessionalSpecialization)
class ProfessionalSpecializationAdmin(admin.ModelAdmin):
    list_display = ['professional', 'category', 'name', 'description_preview']
    list_filter = ['category']
    search_fields = ['professional__name', 'name', 'category__name', 'description']
    autocomplete_fields = ['professional', 'category']

    def description_preview(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else (obj.description or 'No description')
    description_preview.short_description = "Description"

@admin.register(ProfessionalAvailability)
class ProfessionalAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['professional', 'day_of_week', 'start_time', 'end_time', 'is_available']
    list_filter = ['day_of_week', 'is_available']
    search_fields = ['professional__name']
    autocomplete_fields = ['professional']

@admin.register(ProfessionalDocument)
class ProfessionalDocumentAdmin(admin.ModelAdmin):
    list_display = ['professional', 'document_type', 'file_preview', 'verified']
    list_filter = ['document_type', 'verified']
    search_fields = ['professional__name']
    readonly_fields = ['file_preview']
    list_editable = ['verified']

    def file_preview(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">View File</a>', obj.file.url)
        return "No file"
    file_preview.short_description = "File"

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'professional', 'client_id', 'session_type', 
        'status', 'duration', 'cost', 'created_at', 'status_badge'
    ]
    list_filter = [
        'session_type', 'status', 'category', 'created_at',
        'call_quality', 'urgency'
    ]
    search_fields = [
        'professional__name', 'client_id', 'room_id',
        'category__name'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'actual_start', 'ended_at',
        'session_duration', 'financial_summary', 'call_duration_display',
        'has_call_issues_display'
    ]
    list_editable = ['status', 'session_type']
    
    fieldsets = [
        ('Session Information', {
            'fields': [
                'professional', 'client_id', 'session_type', 'status',
                'category', 'room_id', 'urgency', 'mode'
            ]
        }),
        ('Timing', {
            'fields': [
                'scheduled_start', 'actual_start', 'ended_at',
                'duration', 'call_duration_display', 'session_duration'
            ]
        }),
        ('Call Information', {
            'fields': [
                'call_started_at', 'call_ended_at', 'call_quality', 
                'call_issues', 'has_call_issues_display'
            ],
            'classes': ['collapse']
        }),
        ('Financials', {
            'fields': [
                'rate_used', 'cost', 'financial_summary'
            ]
        }),
        ('Ratings & Reviews', {
            'fields': [
                'client_rating', 'client_review'
            ]
        }),
        ('Timestamps', {
            'fields': [
                'created_at', 'updated_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    inlines = [PaymentInline, ChatMessageInline, CallLogInline]
    
    actions = ['mark_completed', 'mark_cancelled', 'mark_active', 'export_session_data']

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'active': 'blue',
            'completed': 'green',
            'cancelled': 'red',
            'disconnected': 'purple',
            'expired': 'gray',
            'declined': 'darkred',
            'in_progress': 'teal'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = "Status"

    def session_duration(self, obj):
        try:
            return f"{obj.total_duration:.1f} minutes"
        except Exception as e:
            logger.error(f"Error calculating session duration for session {obj.id}: {e}")
            return "Error"
    session_duration.short_description = "Actual Duration"

    def call_duration_display(self, obj):
        try:
            return f"{obj.call_duration_minutes} minutes"
        except Exception as e:
            logger.error(f"Error calculating call duration for session {obj.id}: {e}")
            return "Error"
    call_duration_display.short_description = "Call Duration"

    def has_call_issues_display(self, obj):
        try:
            if obj.has_call_issues:
                return format_html('<span style="color: red;">● Yes</span>')
            else:
                return format_html('<span style="color: green;">✓ No</span>')
        except Exception as e:
            logger.error(f"Error checking call issues for session {obj.id}: {e}")
            return format_html('<span style="color: gray;">● Unknown</span>')
    has_call_issues_display.short_description = "Call Issues"

    def financial_summary(self, obj):
        try:
            return format_html(
                "<b>Rate:</b> ${}/min | <b>Total Cost:</b> ${} | <b>Duration:</b> {} min",
                obj.rate_used or 0, obj.cost or 0, obj.duration or 0
            )
        except Exception as e:
            logger.error(f"Error in financial_summary for session {obj.id}: {e}")
            return "Error loading financial data"
    financial_summary.short_description = "Financial Summary"

    def mark_completed(self, request, queryset):
        updated = queryset.update(status='completed', ended_at=timezone.now())
        self.message_user(request, f"Marked {updated} sessions as completed.")
    mark_completed.short_description = "Mark selected sessions as completed"

    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f"Marked {updated} sessions as cancelled.")
    mark_cancelled.short_description = "Mark selected sessions as cancelled"

    def mark_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f"Marked {updated} sessions as active.")
    mark_active.short_description = "Mark selected sessions as active"

    def export_session_data(self, request, queryset):
        self.message_user(request, "Export functionality would be implemented here.")
    export_session_data.short_description = "Export session data (Placeholder)"

@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    list_display = ['session', 'booked_by', 'scheduled_for', 'booked_at', 'notes_preview']
    list_filter = ['scheduled_for', 'booked_at']
    search_fields = ['session__professional__name', 'booked_by', 'notes']
    autocomplete_fields = ['session']
    readonly_fields = ['booked_at']

    def notes_preview(self, obj):
        return obj.notes[:50] + '...' if obj.notes and len(obj.notes) > 50 else (obj.notes or 'No notes')
    notes_preview.short_description = "Notes"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'get_session_professional', 'get_session_client', 'amount', 'status', 'payment_method',
        'created_at', 'status_badge', 'is_successful'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = [
        'session__professional__name', 
        'session__client_id',
        'transaction_id',
        'merchant_request_id',
        'checkout_request_id',
        'phone_number',
        'receipt_number'
    ]
    readonly_fields = [
        'created_at', 'completed_at', 'mpesa_details', 
        'transaction_details', 'is_successful_display'
    ]
    list_editable = ['status']
    
    fieldsets = [
        ('Payment Information', {
            'fields': [
                'session', 'amount', 'status', 'payment_method', 'is_successful_display'
            ]
        }),
        ('Transaction Details', {
            'fields': [
                'transaction_id', 'transaction_details'
            ]
        }),
        ('M-Pesa Specific', {
            'fields': [
                'merchant_request_id', 'checkout_request_id',
                'response_code', 'response_description',
                'customer_message', 'phone_number',
                'receipt_number', 'mpesa_details'
            ],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': [
                'created_at', 'completed_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    actions = ['mark_completed', 'mark_failed', 'process_refunds', 'mark_refunded']

    def get_session_professional(self, obj):
        return obj.session.professional.name if obj.session and obj.session.professional else "No Session"
    get_session_professional.short_description = "Professional"

    def get_session_client(self, obj):
        return obj.session.client_id if obj.session else "No Session"
    get_session_client.short_description = "Client ID"

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'blue',
            'cancelled': 'gray'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = "Status"

    def is_successful(self, obj):
        return obj.is_successful
    is_successful.boolean = True
    is_successful.short_description = "Successful"

    def is_successful_display(self, obj):
        if obj.is_successful:
            return format_html('<span style="color: green;">✓ Payment Successful</span>')
        else:
            return format_html('<span style="color: red;">● Payment Not Successful</span>')
    is_successful_display.short_description = "Payment Status"

    def mpesa_details(self, obj):
        if obj.payment_method == 'mpesa':
            return format_html(
                "<b>Phone:</b> {} | <b>Receipt:</b> {}<br><b>Response:</b> {}<br><b>Customer Message:</b> {}",
                obj.phone_number or 'N/A',
                obj.receipt_number or 'N/A',
                obj.response_description or 'N/A',
                obj.customer_message or 'N/A'
            )
        return "Not an M-Pesa payment"
    mpesa_details.short_description = "M-Pesa Details"

    def transaction_details(self, obj):
        return format_html(
            "<b>Transaction ID:</b> {}<br><b>Method:</b> {}<br><b>Amount:</b> ${}",
            obj.transaction_id or 'Pending',
            obj.get_payment_method_display(),
            obj.amount
        )
    transaction_details.short_description = "Transaction Info"

    def mark_completed(self, request, queryset):
        updated = queryset.update(
            status='completed', 
            completed_at=timezone.now()
        )
        self.message_user(request, f"Marked {updated} payments as completed.")
    mark_completed.short_description = "Mark selected payments as completed"

    def mark_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f"Marked {updated} payments as failed.")
    mark_failed.short_description = "Mark selected payments as failed"

    def mark_refunded(self, request, queryset):
        updated = queryset.update(status='refunded')
        self.message_user(request, f"Marked {updated} payments as refunded.")
    mark_refunded.short_description = "Mark selected payments as refunded"

    def process_refunds(self, request, queryset):
        completed_payments = queryset.filter(status='completed')
        updated = completed_payments.update(status='refunded')
        self.message_user(request, f"Processed refunds for {updated} completed payments.")
    process_refunds.short_description = "Refund completed payments"

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'get_session_professional', 'get_session_client', 'status', 'created_by', 
        'created_at', 'status_badge', 'time_to_resolve_display'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'session__professional__name', 'created_by', 'description']
    readonly_fields = ['created_at', 'resolved_at', 'time_to_resolve_display']
    list_editable = ['status']
    
    fieldsets = [
        ('Dispute Information', {
            'fields': [
                'session', 'title', 'description', 'status'
            ]
        }),
        ('Resolution', {
            'fields': [
                'resolution', 'resolved_at', 'time_to_resolve_display'
            ]
        }),
        ('Metadata', {
            'fields': [
                'created_by', 'created_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    actions = ['resolve_disputes', 'close_disputes', 'reopen_disputes']

    def get_session_professional(self, obj):
        return obj.session.professional.name if obj.session and obj.session.professional else "No Session"
    get_session_professional.short_description = "Professional"

    def get_session_client(self, obj):
        return obj.session.client_id if obj.session else "No Session"
    get_session_client.short_description = "Client ID"

    def status_badge(self, obj):
        colors = {
            'open': 'red',
            'in_progress': 'orange',
            'resolved': 'green',
            'closed': 'gray'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = "Status"

    def time_to_resolve_display(self, obj):
        ttr = obj.time_to_resolve
        if ttr:
            return f"{ttr:.1f} hours"
        return "Not resolved"
    time_to_resolve_display.short_description = "Time to Resolve"

    def resolve_disputes(self, request, queryset):
        updated = queryset.update(
            status='resolved',
            resolved_at=timezone.now()
        )
        self.message_user(request, f"Resolved {updated} disputes.")
    resolve_disputes.short_description = "Resolve selected disputes"

    def close_disputes(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f"Closed {updated} disputes.")
    close_disputes.short_description = "Close selected disputes"

    def reopen_disputes(self, request, queryset):
        updated = queryset.update(status='open', resolved_at=None)
        self.message_user(request, f"Reopened {updated} disputes.")
    reopen_disputes.short_description = "Reopen selected disputes"

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = [
        'get_session_professional', 'get_session_client', 'sender_type', 'message_type', 
        'created_at', 'read', 'message_preview'
    ]
    list_filter = ['sender_type', 'message_type', 'read', 'created_at']
    search_fields = [
        'session__professional__name', 
        'session__client_id',
        'message',
        'content'
    ]
    readonly_fields = ['created_at', 'message_id']
    list_editable = ['read']
    
    fieldsets = [
        ('Message Information', {
            'fields': [
                'session', 'message_id', 'sender_type', 'message_type'
            ]
        }),
        ('Content', {
            'fields': [
                'message', 'content'
            ]
        }),
        ('Status', {
            'fields': [
                'read', 'created_at'
            ]
        })
    ]

    def get_session_professional(self, obj):
        return obj.session.professional.name if obj.session and obj.session.professional else "No Session"
    get_session_professional.short_description = "Professional"

    def get_session_client(self, obj):
        return obj.session.client_id if obj.session else "No Session"
    get_session_client.short_description = "Client ID"

    def message_preview(self, obj):
        content = obj.content or obj.message
        return content[:50] + '...' if content and len(content) > 50 else (content or 'No message')
    message_preview.short_description = "Message"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'user_type', 'phone', 'location', 
        'is_verified', 'created_at', 'user_type_badge'
    ]
    list_filter = ['user_type', 'is_verified', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone', 'location']
    readonly_fields = ['created_at', 'updated_at', 'preferences_display', 'notification_settings_display']
    list_editable = ['user_type', 'is_verified']
    
    fieldsets = [
        ('User Information', {
            'fields': [
                'user', 'user_type', 'is_verified'
            ]
        }),
        ('Contact Details', {
            'fields': [
                'phone', 'date_of_birth', 'location', 'timezone'
            ]
        }),
        ('Profile', {
            'fields': [
                'avatar'
            ]
        }),
        ('Preferences', {
            'fields': [
                'preferences', 'preferences_display', 
                'notification_preferences', 'notification_settings',
                'notification_settings_display'
            ],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': [
                'created_at', 'updated_at'
            ],
            'classes': ['collapse']
        })
    ]

    def user_type_badge(self, obj):
        colors = {
            'client': 'blue',
            'professional': 'green',
            'admin': 'red'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.user_type, 'gray'),
            obj.get_user_type_display().upper()
        )
    user_type_badge.short_description = "User Type"

    def preferences_display(self, obj):
        if obj.preferences:
            return format_html("<pre>{}</pre>", str(obj.preferences))
        return "No preferences set"
    preferences_display.short_description = "Preferences (Formatted)"

    def notification_settings_display(self, obj):
        if obj.notification_settings:
            return format_html("<pre>{}</pre>", str(obj.notification_settings))
        return "No notification settings"
    notification_settings_display.short_description = "Notification Settings (Formatted)"

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'notification_type', 'read', 
        'priority', 'created_at', 'read_status', 'priority_badge'
    ]
    list_filter = [
        'notification_type', 'read', 'priority', 'created_at'
    ]
    search_fields = ['title', 'message', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'data_display']
    list_editable = ['read', 'priority']
    
    fieldsets = [
        ('Notification Content', {
            'fields': [
                'user', 'notification_type', 'title', 'message'
            ]
        }),
        ('Settings', {
            'fields': [
                'priority', 'priority_badge', 'read'
            ]
        }),
        ('Related Objects', {
            'fields': [
                'related_session'
            ],
            'classes': ['collapse']
        }),
        ('Actions & Data', {
            'fields': [
                'action_url', 'data', 'data_display'
            ],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': [
                'created_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    actions = ['mark_as_read', 'mark_as_unread', 'mark_high_priority']

    def read_status(self, obj):
        if obj.read:
            return format_html('<span style="color: green;">✓ Read</span>')
        else:
            return format_html('<span style="color: orange;">● Unread</span>')
    read_status.short_description = "Read Status"

    def priority_badge(self, obj):
        colors = {
            'low': 'gray',
            'medium': 'blue',
            'high': 'orange'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.priority, 'gray'),
            obj.get_priority_display().upper()
        )
    priority_badge.short_description = "Priority"

    def data_display(self, obj):
        if obj.data:
            return format_html("<pre>{}</pre>", str(obj.data))
        return "No additional data"
    data_display.short_description = "Data (Formatted)"

    def mark_as_read(self, request, queryset):
        updated = queryset.update(read=True)
        self.message_user(request, f"Marked {updated} notifications as read.")
    mark_as_read.short_description = "Mark selected as read"

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(read=False)
        self.message_user(request, f"Marked {updated} notifications as unread.")
    mark_as_unread.short_description = "Mark selected as unread"

    def mark_high_priority(self, request, queryset):
        updated = queryset.update(priority='high')
        self.message_user(request, f"Marked {updated} notifications as high priority.")
    mark_high_priority.short_description = "Mark selected as high priority"

@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = [
        'get_session_professional', 'get_session_client', 'call_type', 'status', 'start_time',
        'duration_minutes', 'call_quality', 'has_technical_issues_badge'  # OK in list_display
    ]
    list_filter = [
        'call_type', 'status', 'call_quality', 'start_time'
    ]
    search_fields = [
        'session__professional__name',
        'session__client_id',
        'client_device',
        'professional_device'
    ]
    readonly_fields = ['start_time', 'end_time', 'technical_details', 'network_details', 'duration_minutes']  # ADD 'duration_minutes' here
    
    fieldsets = [
        ('Call Information', {
            'fields': [
                'session', 'call_type', 'status'
            ]
        }),
        ('Timing', {
            'fields': [
                'start_time', 'end_time', 'duration'  # REMOVE 'duration_minutes' from here
            ]
        }),
        ('Quality Assessment', {
            'fields': [
                'call_quality', 'connection_quality'
            ]
        }),
        ('Technical Details', {
            'fields': [
                'client_device', 'professional_device',
                'audio_issues', 'video_issues', 'network_conditions',
                'technical_details', 'network_details'
            ],
            'classes': ['collapse']
        })
    ]
    
    inlines = [CallIssueReportInline]

    def get_session_professional(self, obj):
        return obj.session.professional.name if obj.session and obj.session.professional else "No Session"
    get_session_professional.short_description = "Professional"

    def get_session_client(self, obj):
        return obj.session.client_id if obj.session else "No Session"
    get_session_client.short_description = "Client ID"

    def duration_minutes(self, obj):
        return f"{obj.duration_minutes} min"
    duration_minutes.short_description = "Duration"

    def has_technical_issues_badge(self, obj):
        if obj.has_technical_issues:
            return format_html('<span style="color: red;">● Yes</span>')
        else:
            return format_html('<span style="color: green;">✓ No</span>')
    has_technical_issues_badge.short_description = "Tech Issues"

    def technical_details(self, obj):
        issues = []
        if obj.audio_issues:
            issues.append(f"Audio: {', '.join(obj.audio_issues)}")
        if obj.video_issues:
            issues.append(f"Video: {', '.join(obj.video_issues)}")
        
        return format_html(
            "<b>Devices:</b> Client: {} | Professional: {}<br><b>Issues:</b> {}",
            obj.client_device or 'Unknown',
            obj.professional_device or 'Unknown',
            ' | '.join(issues) if issues else 'None'
        )
    technical_details.short_description = "Technical Summary"

    def network_details(self, obj):
        if obj.network_conditions:
            return format_html("<pre>{}</pre>", str(obj.network_conditions))
        return "No network data"
    network_details.short_description = "Network Conditions"

@admin.register(CallAnalytics)
class CallAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'professional', 'date', 'total_calls', 'completed_calls',
        'success_rate_display', 'average_duration_display', 'avg_quality_score_display',
        'issue_rate_display'
    ]
    list_filter = ['date', 'professional']
    search_fields = ['professional__name']
    readonly_fields = [
        'created_at', 'updated_at', 'success_rate_display', 
        'issue_rate_display', 'analytics_summary', 'performance_metrics'
    ]
    
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'professional', 'date'
            ]
        }),
        ('Call Statistics', {
            'fields': [
                'total_calls', 'completed_calls', 'failed_calls', 'missed_calls'
            ]
        }),
        ('Duration & Quality', {
            'fields': [
                'total_duration', 'total_duration_minutes', 'avg_call_duration', 
                'avg_quality_score', 'avg_quality_score_display'
            ]
        }),
        ('Performance Metrics', {
            'fields': [
                'technical_issues', 'success_rate', 'average_rating',
                'performance_metrics'
            ]
        }),
        ('Summary', {
            'fields': [
                'success_rate_display', 'issue_rate_display', 'analytics_summary'
            ]
        }),
        ('Timestamps', {
            'fields': [
                'created_at', 'updated_at'
            ],
            'classes': ['collapse']
        })
    ]

    def success_rate_display(self, obj):
        return f"{obj.success_rate:.1f}%"
    success_rate_display.short_description = "Success Rate"

    def average_duration_display(self, obj):
        return f"{obj.avg_call_duration:.1f} min"
    average_duration_display.short_description = "Avg Duration"

    def avg_quality_score_display(self, obj):
        return f"{obj.avg_quality_score:.1f}/5"
    avg_quality_score_display.short_description = "Avg Quality"

    def issue_rate_display(self, obj):
        return f"{obj.issue_rate:.1f}%"
    issue_rate_display.short_description = "Issue Rate"

    def performance_metrics(self, obj):
        return format_html(
            "<b>Call Success:</b> {}<br><b>Average Quality:</b> {}<br><b>Issue Rate:</b> {}",
            self.success_rate_display(obj),
            self.avg_quality_score_display(obj),
            self.issue_rate_display(obj)
        )
    performance_metrics.short_description = "Performance Overview"

    def analytics_summary(self, obj):
        return format_html(
            "<b>Total Calls:</b> {} | <b>Completed:</b> {} | <b>Success Rate:</b> {}<br>"
            "<b>Avg Duration:</b> {} | <b>Avg Quality:</b> {} | <b>Issue Rate:</b> {}",
            obj.total_calls, obj.completed_calls, self.success_rate_display(obj),
            self.average_duration_display(obj), self.avg_quality_score_display(obj), 
            self.issue_rate_display(obj)
        )
    analytics_summary.short_description = "Complete Analytics Summary"

@admin.register(CallRecording)
class CallRecordingAdmin(admin.ModelAdmin):
    list_display = [
        'get_session_professional', 'get_session_client', 'status', 'duration_minutes_display', 
        'file_size_mb_display', 'client_consent', 'professional_consent',
        'available_for_download', 'created_at', 'consent_status'
    ]
    list_filter = ['status', 'storage_location', 'created_at']
    search_fields = ['session__professional__name', 'session__client_id']
    readonly_fields = [
        'created_at', 'processed_at', 'file_size_mb_display', 
        'duration_minutes_display', 'consent_status', 'file_info'
    ]
    list_editable = ['status', 'available_for_download']
    
    fieldsets = [
        ('Recording Information', {
            'fields': [
                'session', 'call_log', 'status'
            ]
        }),
        ('File Details', {
            'fields': [
                'file_path', 'file_size', 'duration',
                'file_size_mb_display', 'duration_minutes_display', 'file_info'
            ]
        }),
        ('Storage & Processing', {
            'fields': [
                'storage_location', 'processed_at'
            ]
        }),
        ('Consent & Permissions', {
            'fields': [
                'client_consent', 'professional_consent',
                'available_for_download', 'consent_status'
            ]
        }),
        ('Timestamps', {
            'fields': [
                'created_at'
            ],
            'classes': ['collapse']
        })
    ]

    def get_session_professional(self, obj):
        return obj.session.professional.name if obj.session and obj.session.professional else "No Session"
    get_session_professional.short_description = "Professional"

    def get_session_client(self, obj):
        return obj.session.client_id if obj.session else "No Session"
    get_session_client.short_description = "Client ID"

    def duration_minutes_display(self, obj):
        return f"{obj.duration_minutes} min"
    duration_minutes_display.short_description = "Duration"

    def file_size_mb_display(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb_display.short_description = "File Size"

    def consent_status(self, obj):
        if obj.client_consent and obj.professional_consent:
            return format_html('<span style="color: green;">✓ Full Consent</span>')
        elif obj.client_consent or obj.professional_consent:
            return format_html('<span style="color: orange;">● Partial Consent</span>')
        else:
            return format_html('<span style="color: red;">● No Consent</span>')
    consent_status.short_description = "Consent Status"

    def file_info(self, obj):
        return format_html(
            "<b>Duration:</b> {}<br><b>File Size:</b> {}<br><b>Storage:</b> {}",
            self.duration_minutes_display(obj),
            self.file_size_mb_display(obj),
            obj.storage_location
        )
    file_info.short_description = "File Information"

@admin.register(CallIssueReport)
class CallIssueReportAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'get_session_professional', 'get_session_client', 'issue_type', 'priority',
        'resolved', 'reported_at', 'resolved_at', 'priority_badge', 'resolution_status'
    ]
    list_filter = [
        'issue_type', 'priority', 'resolved', 'reported_at'
    ]
    search_fields = [
        'title', 'session__professional__name',
        'session__client_id', 'reported_by', 'resolution_notes'
    ]
    readonly_fields = ['reported_at', 'resolved_at', 'resolution_time', 'issue_details']
    list_editable = ['priority', 'resolved']
    
    fieldsets = [
        ('Issue Information', {
            'fields': [
                'session', 'call_log', 'issue_type', 'priority', 'priority_badge'
            ]
        }),
        ('Description', {
            'fields': [
                'title', 'description', 'issue_details'
            ]
        }),
        ('Technical Details', {
            'fields': [
                'steps_to_reproduce', 'expected_behavior', 'actual_behavior'
            ],
            'classes': ['collapse']
        }),
        ('Resolution', {
            'fields': [
                'resolved', 'resolution_status', 'resolution_notes', 'resolved_by',
                'resolved_at', 'resolution_time'
            ]
        }),
        ('Reporting', {
            'fields': [
                'reported_by', 'reported_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    actions = ['mark_resolved', 'mark_high_priority', 'mark_critical_priority', 'mark_unresolved']

    def get_session_professional(self, obj):
        return obj.session.professional.name if obj.session and obj.session.professional else "No Session"
    get_session_professional.short_description = "Professional"

    def get_session_client(self, obj):
        return obj.session.client_id if obj.session else "No Session"
    get_session_client.short_description = "Client ID"

    def priority_badge(self, obj):
        colors = {
            'low': 'gray',
            'medium': 'blue',
            'high': 'orange',
            'critical': 'red'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.priority, 'gray'),
            obj.get_priority_display().upper()
        )
    priority_badge.short_description = "Priority"

    def resolution_status(self, obj):
        if obj.resolved:
            return format_html('<span style="color: green;">✓ Resolved</span>')
        else:
            return format_html('<span style="color: orange;">● Unresolved</span>')
    resolution_status.short_description = "Resolution Status"

    def resolution_time(self, obj):
        ttr = obj.time_to_resolve
        if ttr:
            return f"{ttr:.1f} hours"
        return "Not resolved"
    resolution_time.short_description = "Time to Resolve"

    def issue_details(self, obj):
        return format_html(
            "<b>Type:</b> {} | <b>Priority:</b> {} | <b>Reported by:</b> {}<br><b>Steps:</b> {}",
            obj.get_issue_type_display(),
            obj.get_priority_display(),
            obj.reported_by,
            obj.steps_to_reproduce or 'Not provided'
        )
    issue_details.short_description = "Issue Summary"

    def mark_resolved(self, request, queryset):
        updated = queryset.update(
            resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user.username
        )
        self.message_user(request, f"Marked {updated} issues as resolved.")
    mark_resolved.short_description = "Mark selected issues as resolved"

    def mark_unresolved(self, request, queryset):
        updated = queryset.update(
            resolved=False,
            resolved_at=None,
            resolved_by=''
        )
        self.message_user(request, f"Marked {updated} issues as unresolved.")
    mark_unresolved.short_description = "Mark selected issues as unresolved"

    def mark_high_priority(self, request, queryset):
        updated = queryset.update(priority='high')
        self.message_user(request, f"Marked {updated} issues as high priority.")
    mark_high_priority.short_description = "Mark selected as high priority"

    def mark_critical_priority(self, request, queryset):
        updated = queryset.update(priority='critical')
        self.message_user(request, f"Marked {updated} issues as critical priority.")
    mark_critical_priority.short_description = "Mark selected as critical priority"

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'professional', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'user__email', 'professional__name']
    readonly_fields = ['created_at']
    autocomplete_fields = ['user', 'professional']

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'receipt_number', 'get_payment_session', 'client_name', 'professional_name',
        'amount', 'payment_method', 'issue_date', 'transaction_id'
    ]
    list_filter = ['issue_date', 'payment_method']
    search_fields = [
        'receipt_number', 'client_name', 'professional_name',
        'transaction_id', 'payment__session__professional__name'
    ]
    readonly_fields = ['receipt_number', 'issue_date', 'issue_time', 'receipt_details']
    autocomplete_fields = ['payment', 'session']

    def get_payment_session(self, obj):
        return f"Session {obj.session.id}" if obj.session else "No Session"
    get_payment_session.short_description = "Session"

    def receipt_details(self, obj):
        return format_html(
            "<b>Receipt Number:</b> {}<br>"
            "<b>Client:</b> {}<br>"
            "<b>Professional:</b> {}<br>"
            "<b>Service:</b> {}<br>"
            "<b>Amount:</b> ${}<br>"
            "<b>Transaction ID:</b> {}<br>"
            "<b>Method:</b> {}",
            obj.receipt_number,
            obj.client_name,
            obj.professional_name,
            obj.service_type,
            obj.amount,
            obj.transaction_id,
            obj.payment_method
        )
    receipt_details.short_description = "Receipt Information"

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'user', 'category', 'priority', 'status',
        'created_at', 'status_badge', 'priority_badge'
    ]
    list_filter = ['category', 'priority', 'status', 'created_at']
    search_fields = ['subject', 'user__username', 'user__email', 'message']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at', 'ticket_details']
    list_editable = ['priority', 'status']
    
    actions = ['mark_in_progress', 'mark_resolved', 'mark_closed', 'escalate_priority']

    def status_badge(self, obj):
        colors = {
            'open': 'red',
            'in_progress': 'orange',
            'resolved': 'green',
            'closed': 'gray'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        colors = {
            'low': 'gray',
            'medium': 'blue',
            'high': 'orange',
            'urgent': 'red'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.priority, 'gray'),
            obj.get_priority_display().upper()
        )
    priority_badge.short_description = "Priority"

    def ticket_details(self, obj):
        return format_html(
            "<b>Category:</b> {}<br>"
            "<b>Priority:</b> {}<br>"
            "<b>Status:</b> {}<br>"
            "<b>Created:</b> {}<br>"
            "<b>Updated:</b> {}<br>"
            "<b>Resolved:</b> {}",
            obj.get_category_display(),
            obj.get_priority_display(),
            obj.get_status_display(),
            obj.created_at,
            obj.updated_at,
            obj.resolved_at or "Not resolved"
        )
    ticket_details.short_description = "Ticket Information"

    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f"Marked {updated} tickets as in progress.")
    mark_in_progress.short_description = "Mark selected as in progress"

    def mark_resolved(self, request, queryset):
        updated = queryset.update(status='resolved', resolved_at=timezone.now())
        self.message_user(request, f"Marked {updated} tickets as resolved.")
    mark_resolved.short_description = "Mark selected as resolved"

    def mark_closed(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f"Marked {updated} tickets as closed.")
    mark_closed.short_description = "Mark selected as closed"

    def escalate_priority(self, request, queryset):
        updated = queryset.update(priority='urgent')
        self.message_user(request, f"Escalated {updated} tickets to urgent priority.")
    escalate_priority.short_description = "Escalate to urgent priority"

# ============ VIDEO CALL MODELS ============

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'video_call_balance', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'phone', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'phone', 'date_of_birth', 'emergency_contact')
        }),
        ('Financial', {
            'fields': ('video_call_balance',)
        }),
        ('Media', {
            'fields': ('profile_picture',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    list_per_page = 20

@admin.register(VideoSession)
class VideoSessionAdmin(admin.ModelAdmin):
    list_display = [
        'room_id', 'professional', 'client', 'status', 'formatted_duration',
        'actual_cost', 'payment_status', 'created_at', 'session_status_badge'
    ]
    list_filter = [
        'status', 'payment_status', 'call_quality', 'created_at',
        'professional', 'client'
    ]
    search_fields = [
        'room_id', 'professional__name', 'client__name',
        'payment_reference', 'room_name'
    ]
    readonly_fields = [
        'id', 'room_id', 'created_at', 'actual_start', 'call_started_at',
        'call_ended_at', 'call_duration', 'estimated_cost', 'actual_cost',
        'cost_per_second', 'professional_rate', 'formatted_duration',
        'is_active', 'is_ended', 'can_be_rated', 'session_summary'
    ]
    fieldsets = (
        ('Session Information', {
            'fields': ('id', 'room_id', 'room_name', 'status', 'professional', 'client')
        }),
        ('Timing & Duration', {
            'fields': (
                'created_at', 'scheduled_start', 'actual_start',
                'call_started_at', 'call_ended_at', 'call_duration',
                'formatted_duration', 'max_duration', 'warning_threshold'
            )
        }),
        ('Financial Details', {
            'fields': (
                'professional_rate', 'cost_per_second',
                'estimated_cost', 'actual_cost', 'payment_method',
                'payment_status', 'payment_reference', 'payment_confirmed',
                'payment_confirmed_at', 'session_summary'
            )
        }),
        ('Technical Details', {
            'fields': (
                'call_quality', 'network_stability', 'platform',
                'device_info', 'ip_address', 'recording_enabled',
                'recording_url'
            )
        }),
        ('Media Settings', {
            'fields': (
                'client_video_enabled', 'client_audio_enabled',
                'professional_video_enabled', 'professional_audio_enabled'
            ),
            'classes': ('collapse',)
        }),
        ('Ratings & Feedback', {
            'fields': (
                'client_rating', 'client_feedback',
                'professional_rating', 'professional_feedback'
            )
        }),
        ('Additional Information', {
            'fields': (
                'is_test_call', 'requires_followup',
                'followup_scheduled', 'call_data', 'error_log'
            ),
            'classes': ('collapse',)
        }),
        ('Computed Properties', {
            'fields': ('is_active', 'is_ended', 'can_be_rated'),
            'classes': ('collapse',)
        }),
    )
    inlines = [VideoCallLogInline, VideoCallPaymentInline]
    actions = ['mark_as_completed', 'mark_as_failed', 'process_payments', 'export_video_sessions']
    list_per_page = 25
    
    def session_status_badge(self, obj):
        colors = {
            'initializing': 'gray',
            'connecting': 'blue',
            'ringing': 'orange',
            'active': 'green',
            'ending': 'yellow',
            'ended': 'darkgreen',
            'failed': 'red',
            'cancelled': 'darkred'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    session_status_badge.short_description = "Status"
    
    def session_summary(self, obj):
        return format_html(
            "<b>Professional:</b> {}<br>"
            "<b>Client:</b> {}<br>"
            "<b>Duration:</b> {}<br>"
            "<b>Cost:</b> KSH {}<br>"
            "<b>Quality:</b> {}<br>"
            "<b>Payment Status:</b> {}",
            obj.professional.name,
            obj.client.name,
            obj.formatted_duration,
            obj.actual_cost,
            obj.call_quality,
            obj.get_payment_status_display()
        )
    session_summary.short_description = "Session Summary"
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        for session in queryset:
            if session.status not in ['ended', 'completed']:
                session.status = 'ended'
                session.call_ended_at = timezone.now()
                session.save()
        self.message_user(request, f"{queryset.count()} video sessions marked as completed.")
    mark_as_completed.short_description = "Mark selected video sessions as completed"
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f"{updated} video sessions marked as failed.")
    mark_as_failed.short_description = "Mark selected video sessions as failed"
    
    def process_payments(self, request, queryset):
        self.message_user(request, f"Payment processing initiated for {queryset.count()} video sessions.")
    process_payments.short_description = "Process payments for selected video sessions"
    
    def export_video_sessions(self, request, queryset):
        self.message_user(request, "Export functionality would be implemented here.")
    export_video_sessions.short_description = "Export video session data"

@admin.register(VideoCallLog)
class VideoCallLogAdmin(admin.ModelAdmin):
    list_display = ['session', 'event_type', 'timestamp', 'created_by', 'event_badge']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['session__room_id', 'event_data', 'created_by__username']
    readonly_fields = ['session', 'event_type', 'event_data', 'timestamp', 'created_by', 'event_details']
    list_per_page = 50
    
    def event_badge(self, obj):
        colors = {
            'call_initiated': 'blue',
            'call_answered': 'green',
            'call_ended': 'darkgreen',
            'call_failed': 'red',
            'quality_change': 'orange',
            'mute_toggle': 'gray',
            'video_toggle': 'purple',
            'camera_switch': 'teal',
            'network_change': 'brown',
            'payment_processed': 'darkblue',
            'rating_submitted': 'gold'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.event_type, 'gray'),
            obj.get_event_type_display().upper()
        )
    event_badge.short_description = "Event Type"
    
    def event_details(self, obj):
        return format_html("<pre>{}</pre>", str(obj.event_data))
    event_details.short_description = "Event Data"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(VideoCallPayment)
class VideoCallPaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'session', 'amount', 'currency', 'status', 'initiated_at', 'payment_status_badge']
    list_filter = ['status', 'payment_gateway', 'initiated_at']
    search_fields = ['transaction_id', 'session__room_id', 'session__professional__name']
    readonly_fields = [
        'session', 'amount', 'currency', 'transaction_id', 'payment_gateway',
        'gateway_response', 'initiated_at', 'completed_at', 'receipt_url',
        'payment_details'
    ]
    list_per_page = 20
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'purple'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display().upper()
        )
    payment_status_badge.short_description = "Status"
    
    def payment_details(self, obj):
        return format_html(
            "<b>Transaction ID:</b> {}<br>"
            "<b>Gateway:</b> {}<br>"
            "<b>Amount:</b> {} {}<br>"
            "<b>Initiated:</b> {}<br>"
            "<b>Completed:</b> {}",
            obj.transaction_id,
            obj.payment_gateway,
            obj.amount, obj.currency,
            obj.initiated_at,
            obj.completed_at or 'Not completed'
        )
    payment_details.short_description = "Payment Information"

@admin.register(VideoCallRecording)
class VideoCallRecordingAdmin(admin.ModelAdmin):
    list_display = ['recording_id', 'session', 'duration', 'file_size_mb', 'created_at', 'is_processed', 'recording_status_badge']
    list_filter = ['is_processed', 'created_at']
    search_fields = ['recording_id', 'session__room_id', 'storage_url']
    readonly_fields = [
        'session', 'recording_id', 'storage_url', 'storage_path',
        'file_size', 'duration', 'format', 'created_at',
        'recording_details'
    ]
    list_per_page = 20
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_mb.short_description = "File Size"
    
    def recording_status_badge(self, obj):
        if obj.is_processed:
            return format_html('<span style="background: green; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">PROCESSED</span>')
        else:
            return format_html('<span style="background: orange; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">PENDING</span>')
    recording_status_badge.short_description = "Processing Status"
    
    def recording_details(self, obj):
        return format_html(
            "<b>Recording ID:</b> {}<br>"
            "<b>Duration:</b> {} seconds<br>"
            "<b>File Size:</b> {} MB<br>"
            "<b>Format:</b> {}<br>"
            "<b>Storage:</b> {}<br>"
            "<b>URL:</b> {}",
            obj.recording_id,
            obj.duration,
            self.file_size_mb(obj),
            obj.format,
            obj.storage_location,
            obj.storage_url or 'Not available'
        )
    recording_details.short_description = "Recording Information"

# ============ CUSTOM USER ADMIN ============

class CustomUserAdmin(UserAdmin):
    inlines = [UserProfileInline]
    list_display = UserAdmin.list_display + ('get_user_type', 'get_phone', 'get_joined_date', 'is_active_status')
    
    def get_user_type(self, obj):
        try:
            return obj.userprofile.user_type
        except ObjectDoesNotExist:
            return "No profile"
    get_user_type.short_description = 'User Type'
    
    def get_phone(self, obj):
        try:
            return obj.userprofile.phone
        except ObjectDoesNotExist:
            return "No phone"
    get_phone.short_description = 'Phone'

    def get_joined_date(self, obj):
        try:
            return obj.userprofile.created_at
        except ObjectDoesNotExist:
            return "No profile"
    get_joined_date.short_description = 'Profile Created'

    def is_active_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">● Inactive</span>')
    is_active_status.short_description = 'Active Status'

# ============ REGISTRATION ============

# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Admin site customization
admin.site.site_header = "TeleConnect Administration"
admin.site.site_title = "TeleConnect Admin Portal"
admin.site.index_title = "Welcome to TeleConnect Administration"

# ============ ERROR HANDLING ============

def handle_admin_error(view_func):
    """Decorator to handle errors in admin views"""
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Admin error in {view_func.__name__}: {e}")
            raise
    return wrapper

# Apply error handling to all admin views
for model, admin_class in admin.site._registry.items():
    for method_name in ['changelist_view', 'add_view', 'change_view', 'delete_view']:
        if hasattr(admin_class, method_name):
            original_method = getattr(admin_class, method_name)
            setattr(admin_class, method_name, handle_admin_error(original_method))
