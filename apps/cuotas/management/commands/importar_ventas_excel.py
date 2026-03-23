"""
Management command para importar ventas desde Excel.

Uso:
    python manage.py importar_ventas_excel --org-slug faparca --file ventas.xlsx [--dry-run]
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import Organization


class Command(BaseCommand):
    help = 'Importar cuotas/ventas desde un archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument('--org-slug', required=True, help='Slug de la organización')
        parser.add_argument('--file', required=True, help='Ruta al archivo Excel')
        parser.add_argument('--dry-run', action='store_true', help='Solo verificar sin guardar')

    def handle(self, *args, **options):
        slug = options['org_slug']
        filepath = options['file']
        dry_run = options['dry_run']

        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Organización "{slug}" no encontrada.'))
            return

        self.stdout.write(f'Importando desde {filepath} para org "{org.name}"...')

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo DRY-RUN: no se guardarán datos.'))

        # Simular request con org
        class FakeRequest:
            pass
        fake_req = FakeRequest()
        fake_req.org = org

        from apps.cuotas.views import _procesar_excel

        with open(filepath, 'rb') as f:
            if dry_run:
                from django.db import transaction
                try:
                    with transaction.atomic():
                        resultado = _procesar_excel(fake_req, f)
                        self.stdout.write(self.style.SUCCESS(
                            f'DRY-RUN: {resultado["creados"]} serían creados, '
                            f'{resultado["actualizados"]} serían actualizados.'
                        ))
                        if resultado['errores']:
                            for err in resultado['errores']:
                                self.stderr.write(self.style.WARNING(f'  {err}'))
                        raise transaction.TransactionManagementError('rollback')
                except transaction.TransactionManagementError:
                    pass
            else:
                resultado = _procesar_excel(fake_req, f)
                self.stdout.write(self.style.SUCCESS(
                    f'Importación completada: {resultado["creados"]} creados, '
                    f'{resultado["actualizados"]} actualizados.'
                ))
                if resultado['errores']:
                    self.stdout.write(self.style.WARNING(f'{len(resultado["errores"])} errores:'))
                    for err in resultado['errores']:
                        self.stderr.write(f'  {err}')
