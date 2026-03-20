import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.models import Organization

User = get_user_model()
org, _ = Organization.objects.get_or_create(name='Test Org', slug='test-org', is_active=True)

if not User.objects.filter(email='test@example.com').exists():
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpassword123',
        role='gerente',
        organization=org
    )
    print("Test user created: test@example.com / testpassword123")
else:
    print("Test user already exists: test@example.com / testpassword123")
