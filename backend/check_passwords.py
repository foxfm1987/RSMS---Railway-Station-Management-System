import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from appname.models import User

users = User.objects.exclude(role='PASSENGER')
for u in users:
    pwd_check = u.check_password('password123')
    print(f'{u.email}: password123 = {pwd_check}')
