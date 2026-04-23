import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.contrib.auth.hashers import make_password
from appname.models import User

users = [
    ("admin", "STATION_MASTER"),
    ("goods1", "GOODS_MANAGER"),
    ("ticket1", "TICKET_STAFF"),
    ("ticket2", "TICKET_STAFF"),
    ("ticket3", "TICKET_STAFF"),
    ("staff1", "STORE_STAFF"),
    ("staff2", "STORE_STAFF"),
    ("staff3", "STORE_STAFF"),
    ("staff4", "STORE_STAFF"),
    ("staff5", "STORE_STAFF"),
    ("staff6", "STORE_STAFF"),
]

for username, role in users:
    email = f"{username}@station.local"
    obj, created = User.objects.get_or_create(
        email=email,
        defaults={
            "password": make_password(username),
            "role": role,
            "is_staff": True,
            "fullname": username,
        },
    )
    if not created:
        obj.role = role
        obj.is_staff = True
        obj.fullname = username
        obj.set_password(username)
        obj.save()

print("Staff users seeded.")
