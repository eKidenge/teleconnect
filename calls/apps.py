from django.apps import AppConfig

class CallsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calls'
    
    def ready(self):
        # Import signals if you add them later
        try:
            import calls.signals
        except ImportError:
            pass
