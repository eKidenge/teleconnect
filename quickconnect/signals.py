# consultations/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Session, CallLog, Professional, Notification

@receiver(pre_save, sender=Session)
def handle_session_status_change(sender, instance, **kwargs):
    """Handle session status changes"""
    if instance.id:
        try:
            old_instance = Session.objects.get(id=instance.id)
            if old_instance.status != instance.status:
                # Status changed - handle accordingly
                if instance.status == 'active' and instance.call_started_at is None:
                    instance.call_started_at = timezone.now()
                elif instance.status in ['completed', 'cancelled', 'disconnected']:
                    if instance.ended_at is None:
                        instance.ended_at = timezone.now()
        except Session.DoesNotExist:
            pass

@receiver(post_save, sender=CallLog)
def handle_call_log_creation(sender, instance, created, **kwargs):
    """Handle new call log entries"""
    if created:
        # Update professional call statistics
        professional = instance.session.professional
        professional.total_calls += 1
        professional.save()

@receiver(post_save, sender=Session)
def handle_call_timeout(sender, instance, created, **kwargs):
    """Handle call timeouts for pending sessions"""
    if instance.status == 'pending' and instance.created_at:
        # If session has been pending for more than 30 seconds, mark as missed
        time_since_creation = (timezone.now() - instance.created_at).total_seconds()
        if time_since_creation > 30:  # 30 seconds timeout
            instance.status = 'expired'
            instance.save()
