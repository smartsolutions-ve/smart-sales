"""Management command para limpiar mensajes antiguos del chat IA."""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.chat_ia.models import ChatMensaje


class Command(BaseCommand):
    help = 'Elimina mensajes del chat IA con más de N días de antigüedad.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=90,
            help='Eliminar mensajes con más de estos días (default: 90)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo mostrar cuántos mensajes se eliminarían',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        dry_run = options['dry_run']
        limite = timezone.now() - timedelta(days=dias)

        qs = ChatMensaje.objects.filter(created_at__lt=limite)
        count = qs.count()

        if dry_run:
            self.stdout.write(f'Se eliminarían {count} mensajes con más de {dias} días.')
            return

        if count == 0:
            self.stdout.write('No hay mensajes antiguos para eliminar.')
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'Eliminados {count} mensajes con más de {dias} días.'))
