"""
Crea el superadmin inicial de SmartSales.
Uso: python manage.py create_superadmin
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User


class Command(BaseCommand):
    help = 'Crea el superadmin inicial de SmartSales'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', help='Nombre de usuario (default: admin)')
        parser.add_argument('--email', default='admin@smartsales.com.ve', help='Email del admin')
        parser.add_argument('--password', default=None, help='Contraseña (se pide interactivamente si no se provee)')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'El usuario "{username}" ya existe.'))
            return

        if not password:
            import getpass
            password = getpass.getpass(f'Contraseña para "{username}": ')
            password2 = getpass.getpass('Confirmar contraseña: ')
            if password != password2:
                self.stdout.write(self.style.ERROR('Las contraseñas no coinciden.'))
                return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role='superadmin',
            organization=None,
            is_staff=True,
            is_superuser=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Superadmin "{user.username}" creado exitosamente.\n'
            f'Accede en: http://127.0.0.1:8000/login/'
        ))
