import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from appname.models import TrainSchedule
from django.utils import timezone

today = timezone.localdate()
deleted, _ = TrainSchedule.objects.filter(service_date=today).delete()
print(f'✓ Deleted {deleted} existing schedules for {today}')

# Now call the reset_schedule command via Django's call_command
from django.core.management import call_command
call_command('reset_schedule')
