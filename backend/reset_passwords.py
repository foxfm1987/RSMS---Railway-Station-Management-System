import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from appname.models import User
from django.contrib.auth.hashers import make_password

# Reset all staff passwords to 'password123'
staff_users = User.objects.exclude(role='PASSENGER')
for user in staff_users:
    user.password = make_password('password123')
    user.save()
    print(f'Reset password for {user.email} ({user.role})')

print('\nAll staff passwords reset to: password123')
