import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
username = getattr(settings, "ADMIN_USERNAME", "Harsha")
password = getattr(settings, "ADMIN_PASSWORD", "vamsi")
email = os.environ.get("ADMIN_EMAIL", "harsha@cinebook.local")

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
        "is_staff": True,
        "is_superuser": True,
    },
)

user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

if created:
    print(f"Superuser '{username}' created successfully.")
else:
    print(f"Superuser '{username}' updated successfully.")
