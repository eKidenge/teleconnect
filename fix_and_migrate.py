#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teleconnect.settings')
django.setup()

from django.core.management import call_command

# Recreate migrations for quickconnect and apply them
call_command('makemigrations', 'quickconnect')
call_command('migrate', '--run-syncdb', '--noinput')

# Collect static files
call_command('collectstatic', '--noinput')
