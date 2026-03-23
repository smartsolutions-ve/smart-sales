"""Tests del módulo de flotas."""
import pytest
from decimal import Decimal
from django.urls import reverse
from apps.flotas.models import Vehiculo, Viaje, ViajeDetalle
from .conftest import (
    VehiculoFactory, ViajeFactory, PedidoFactory,
    OrganizationFactory, UserFactory, ClienteFactory,
)


@pytest.mark.django_db
class TestVehiculoModel:

    def test_crear_vehiculo(self, vehiculo):
        assert vehiculo.pk is not None
        assert vehiculo.is_active is True

    def test_str(self, vehiculo):
        assert vehiculo.placa in str(vehiculo)


@pytest.mark.django_db
class TestViajeModel:

    def test_crear_viaje(self, viaje):
        assert viaje.pk is not None
        assert viaje.estado == 'Programado'

    def test_peso_total_vacio(self, viaje):
        assert viaje.peso_total_kg == 0

    def test_peso_total_con_detalles(self, viaje, pedido):
        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal('100'), orden_entrega=1)
        assert viaje.peso_total_kg == Decimal('100')

    def test_porcentaje_utilizacion(self, viaje, pedido):
        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal('2500'), orden_entrega=1)
        assert viaje.porcentaje_utilizacion == 50.0

    def test_puede_eliminarse_programado(self, viaje):
        assert viaje.puede_eliminarse() is True

    def test_no_puede_eliminarse_en_ruta(self, viaje):
        viaje.estado = 'En Ruta'
        viaje.save()
        assert viaje.puede_eliminarse() is False


@pytest.mark.django_db
class TestFlotasViews:

    def test_vehiculos_lista(self, client_gerente):
        url = reverse('flotas:vehiculos')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_vehiculo_crear(self, client_gerente, org):
        url = reverse('flotas:vehiculo_crear')
        resp = client_gerente.post(url, {
            'placa': 'XYZ-999',
            'capacidad_kg': '8000',
            'marca': 'Toyota',
            'modelo': 'Hilux',
            'is_active': 'on',
        })
        assert resp.status_code == 302
        assert Vehiculo.objects.filter(placa='XYZ-999').exists()

    def test_viajes_lista(self, client_gerente):
        url = reverse('flotas:lista')
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_viaje_crear(self, client_gerente, vehiculo, gerente, pedido):
        url = reverse('flotas:crear')
        resp = client_gerente.post(url, {
            'vehiculo': vehiculo.pk,
            'chofer': gerente.pk,
            'fecha': '2026-03-25',
            'pedidos': [pedido.pk],
            f'peso_{pedido.pk}': '500',
        })
        assert resp.status_code == 302
        assert Viaje.objects.count() == 1

    def test_viaje_detalle(self, client_gerente, viaje):
        url = reverse('flotas:detalle', args=[viaje.pk])
        resp = client_gerente.get(url)
        assert resp.status_code == 200

    def test_viaje_cambiar_estado(self, client_gerente, viaje):
        url = reverse('flotas:cambiar_estado', args=[viaje.pk])
        resp = client_gerente.post(url, {'estado': 'En Ruta'})
        assert resp.status_code == 302
        viaje.refresh_from_db()
        assert viaje.estado == 'En Ruta'

    def test_viaje_eliminar_programado(self, client_gerente, viaje):
        url = reverse('flotas:eliminar', args=[viaje.pk])
        resp = client_gerente.post(url)
        assert resp.status_code == 302
        assert not Viaje.objects.filter(pk=viaje.pk).exists()

    def test_viaje_no_eliminar_en_ruta(self, client_gerente, viaje):
        viaje.estado = 'En Ruta'
        viaje.save()
        url = reverse('flotas:eliminar', args=[viaje.pk])
        resp = client_gerente.post(url)
        assert resp.status_code == 302
        assert Viaje.objects.filter(pk=viaje.pk).exists()

    def test_dashboard_flotas(self, client_gerente):
        url = reverse('flotas:dashboard')
        resp = client_gerente.get(url)
        assert resp.status_code == 200
