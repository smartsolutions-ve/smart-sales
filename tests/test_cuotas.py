"""Tests del módulo de cuotas y ventas."""
import pytest
from decimal import Decimal
from django.urls import reverse
from apps.cuotas.models import VentaMensual, TasaCambio, Zona
from .conftest import (
    VentaMensualFactory, ZonaFactory,
    OrganizationFactory, UserFactory,
)


@pytest.mark.django_db
class TestVentaMensualModel:

    def test_crear_venta(self, org):
        v = VentaMensualFactory(organization=org)
        assert v.pk is not None

    def test_cumplimiento_venta(self, org):
        v = VentaMensualFactory(
            organization=org,
            plan_venta_usd=Decimal('1000'),
            real_venta_usd=Decimal('800'),
        )
        assert v.cumplimiento_venta == 80.0

    def test_cumplimiento_cantidad(self, org):
        v = VentaMensualFactory(
            organization=org,
            plan_cantidad=Decimal('200'),
            real_cantidad=Decimal('250'),
        )
        assert v.cumplimiento_cantidad == 125.0

    def test_cumplimiento_sin_plan(self, org):
        v = VentaMensualFactory(
            organization=org,
            plan_venta_usd=Decimal('0'),
            real_venta_usd=Decimal('100'),
        )
        assert v.cumplimiento_venta == 0


@pytest.mark.django_db
class TestZonaModel:

    def test_crear_zona(self, org):
        z = ZonaFactory(organization=org, nombre='Caracas')
        assert str(z) == 'Caracas'


@pytest.mark.django_db
class TestTasaCambio:

    def test_crear_tasa(self, org):
        t = TasaCambio.objects.create(
            organization=org,
            fecha='2026-03-01',
            tasa_bs_por_usd=Decimal('36.5000'),
            fuente='BCV',
        )
        assert t.pk is not None


@pytest.mark.django_db
class TestCuotasViews:

    def test_lista(self, client_gerente):
        url = reverse('cuotas:lista')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_resumen_zona(self, client_gerente, org):
        VentaMensualFactory(organization=org, zona_nombre='Norte')
        url = reverse('cuotas:resumen_zona')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_resumen_vendedor(self, client_gerente, org):
        VentaMensualFactory(organization=org)
        url = reverse('cuotas:resumen_vendedor')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_resumen_producto(self, client_gerente, org):
        VentaMensualFactory(organization=org)
        url = reverse('cuotas:resumen_producto')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_importar_get(self, client_gerente):
        url = reverse('cuotas:importar')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_exportar_csv(self, client_gerente, org):
        VentaMensualFactory(organization=org)
        url = reverse('cuotas:exportar_csv')
        resp = client_gerente.get(url)
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'text/csv'

    def test_tasas_lista(self, client_gerente):
        url = reverse('cuotas:tasas')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_tasa_crear(self, client_gerente, org):
        url = reverse('cuotas:tasa_crear')
        resp = client_gerente.post(url, {
            'fecha': '2026-03-01',
            'tasa_bs_por_usd': '36.5000',
            'fuente': 'BCV',
        })
        assert resp.status_code == 302
        assert TasaCambio.objects.filter(organization=org).exists()

    def test_importar_excel(self, client_gerente, org):
        """Test importar un archivo Excel válido."""
        import openpyxl
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Cuotas'
        ws.append(['periodo', 'vendedor', 'producto', 'codigo', 'zona', 'canal',
                    'plan cantidad', 'plan venta usd', 'real cantidad', 'real venta usd'])
        ws.append(['2026-01-01', 'Juan Pérez', 'Producto A', 'PA-001', 'Norte', 'DIRECTO',
                    100, 5000, 80, 4000])
        ws.append(['2026-01-01', 'María López', 'Producto B', 'PB-001', 'Sur', 'DIRECTO',
                    200, 8000, 190, 7600])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        archivo = SimpleUploadedFile('ventas.xlsx', buffer.read(),
                                      content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        url = reverse('cuotas:importar')
        resp = client_gerente.post(url, {'archivo': archivo})
        assert resp.status_code == 200
        assert VentaMensual.objects.filter(organization=org).count() == 2

    def test_filtro_periodo(self, client_gerente, org):
        VentaMensualFactory(organization=org, periodo='2026-01-01')
        VentaMensualFactory(organization=org, periodo='2026-02-01')
        url = reverse('cuotas:lista') + '?periodo=2026-01'
        resp = client_gerente.get(url)
        assert resp.status_code == 200
