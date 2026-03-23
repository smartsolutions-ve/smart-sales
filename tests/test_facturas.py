"""Tests del módulo de facturación."""
import pytest
from decimal import Decimal
from django.urls import reverse
from apps.pedidos.models import Factura
from .conftest import (
    PedidoFactory, PedidoItemFactory, FacturaFactory,
    OrganizationFactory, UserFactory, ClienteFactory,
)


@pytest.mark.django_db
class TestFacturaModel:

    def test_crear_factura(self, pedido_con_items):
        factura = FacturaFactory(pedido=pedido_con_items, monto=Decimal('300'))
        assert factura.pk is not None
        assert factura.monto == Decimal('300')

    def test_monto_facturado(self, pedido_con_items):
        FacturaFactory(pedido=pedido_con_items, monto=Decimal('200'))
        FacturaFactory(pedido=pedido_con_items, monto=Decimal('150'))
        assert pedido_con_items.monto_facturado == Decimal('350')

    def test_estado_sin_facturar(self, pedido_con_items):
        assert pedido_con_items.estado_facturacion == 'sin_facturar'

    def test_estado_parcial(self, pedido_con_items):
        # Total es 650 (5*100 + 3*50)
        FacturaFactory(pedido=pedido_con_items, monto=Decimal('300'))
        assert pedido_con_items.estado_facturacion == 'parcial'

    def test_estado_facturado(self, pedido_con_items):
        FacturaFactory(pedido=pedido_con_items, monto=pedido_con_items.total)
        assert pedido_con_items.estado_facturacion == 'facturado'

    def test_multiples_facturas_facturado(self, pedido_con_items):
        FacturaFactory(pedido=pedido_con_items, monto=Decimal('400'))
        FacturaFactory(pedido=pedido_con_items, monto=Decimal('250'))
        assert pedido_con_items.estado_facturacion == 'facturado'


@pytest.mark.django_db
class TestFacturaViews:

    def test_agregar_factura(self, client_gerente, pedido_con_items):
        url = reverse('pedidos:factura_crear', args=[pedido_con_items.pk])
        resp = client_gerente.post(url, {
            'numero_factura': 'FAC-001',
            'fecha_factura': '2026-03-01',
            'monto': '500.00',
        })
        assert resp.status_code == 302
        assert Factura.objects.filter(pedido=pedido_con_items).exists()

    def test_agregar_factura_campos_requeridos(self, client_gerente, pedido_con_items):
        url = reverse('pedidos:factura_crear', args=[pedido_con_items.pk])
        resp = client_gerente.post(url, {'numero_factura': '', 'fecha_factura': '', 'monto': ''})
        assert resp.status_code == 302
        assert not Factura.objects.filter(pedido=pedido_con_items).exists()

    def test_eliminar_factura(self, client_gerente, pedido_con_items):
        factura = FacturaFactory(pedido=pedido_con_items, monto=Decimal('100'))
        url = reverse('pedidos:factura_eliminar', args=[factura.pk])
        resp = client_gerente.post(url)
        assert resp.status_code == 302
        assert not Factura.objects.filter(pk=factura.pk).exists()
