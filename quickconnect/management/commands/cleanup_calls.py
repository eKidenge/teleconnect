# consultations/management/commands/cleanup_calls.py
from django.core.management.base import BaseCommand
from consultations.utils import CallManager

class Command(BaseCommand):
    help = 'Clean up expired call sessions'
    
    def handle(self, *args, **options):
        try:
            count = CallManager.cleanup_expired_sessions()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up {count} expired sessions')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error cleaning up sessions: {str(e)}')
            )
