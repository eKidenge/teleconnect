from django.apps import AppConfig
import sys

class QuickconnectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quickconnect'

    def ready(self):
        """Create a superuser automatically on startup (Render Free friendly)"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # ⚠ Change these credentials to whatever you want
            username = 'admin'
            email = 'admin@directconnect.com'
            password = 'admin123'

            if not User.objects.filter(username=username).exists():
                User.objects.create_superuser(username=username, email=email, password=password)
                print(f"✅ Superuser '{username}' created!")
            else:
                print(f"ℹ Superuser '{username}' already exists.")

        except Exception as e:
            # Avoid crashing Render on startup
            print(f"⚠ Superuser creation skipped: {e}", file=sys.stderr)
