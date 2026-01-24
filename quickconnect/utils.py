# consultations/utils.py
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Professional, Session, CallAnalytics

logger = logging.getLogger(__name__)

class CallManager:
    """Utility class for managing voice calls"""
    
    @staticmethod
    def cleanup_expired_sessions():
        """Clean up expired and abandoned sessions"""
        try:
            expired_time = timezone.now() - timedelta(minutes=30)
            expired_sessions = Session.objects.filter(
                status='pending',
                created_at__lt=expired_time
            )
            
            for session in expired_sessions:
                session.status = 'expired'
                session.save()
                
                # Release professional lock
                professional = session.professional
                professional.release_lock()
                professional.save()
                
            return expired_sessions.count()
            
        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}")
            return 0
    
    @staticmethod
    def get_professional_call_stats(professional_id, days=30):
        """Get call statistics for a professional"""
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            stats = {
                'total_calls': 0,
                'completed_calls': 0,
                'average_duration': 0,
                'success_rate': 0,
                'quality_score': 0
            }
            
            analytics = CallAnalytics.objects.filter(
                professional_id=professional_id,
                date__gte=start_date
            )
            
            if analytics.exists():
                stats['total_calls'] = analytics.aggregate(Sum('total_calls'))['total_calls__sum'] or 0
                stats['completed_calls'] = analytics.aggregate(Sum('completed_calls'))['completed_calls__sum'] or 0
                stats['average_duration'] = analytics.aggregate(Avg('average_duration'))['average_duration__avg'] or 0
                
                if stats['total_calls'] > 0:
                    stats['success_rate'] = (stats['completed_calls'] / stats['total_calls']) * 100
                    stats['quality_score'] = analytics.aggregate(Avg('average_quality_score'))['average_quality_score__avg'] or 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Professional stats error: {str(e)}")
            return {}
    
    @staticmethod
    def validate_call_parameters(professional_id, client_id, session_type):
        """Validate call parameters before initiation"""
        try:
            # Check professional exists and is approved
            professional = Professional.objects.get(
                id=professional_id, 
                status='approved'
            )
            
            # Check availability
            if not professional.is_available_for_session:
                return False, "Professional is not available"
            
            # Check session type validity
            valid_session_types = ['audio', 'video']
            if session_type not in valid_session_types:
                return False, "Invalid session type"
            
            return True, "Valid parameters"
            
        except Professional.DoesNotExist:
            return False, "Professional not found"
        except Exception as e:
            logger.error(f"Parameter validation error: {str(e)}")
            return False, "Validation error"
