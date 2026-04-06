"""
Tests Fase 1 — Módulo Flotas

Cubre:
- ViajeDetalle.clean(): peso válido, peso excesivo, acumulación, actualización
- Viaje.puede_eliminarse(): Programado / En Ruta / Completado / Cancelado
- Viaje.peso_total_kg y porcentaje_utilizacion
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.flotas.models import Viaje, ViajeDetalle

from tests.conftest import (
    OrganizationFactory, UserFactory, ClienteFactory,
    PedidoFactory, VehiculoFactory, ViajeFactory,
)


# ── ViajeDetalle.clean ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestViajeDetalleClean:

    def _viaje(self, capacidad_kg=Decimal('5000.00')):
        org = OrganizationFactory()
        vehiculo = VehiculoFactory(organization=org, capacidad_kg=capacidad_kg)
        chofer = UserFactory(organization=org)
        viaje = ViajeFactory(organization=org, vehiculo=vehiculo, chofer=chofer)
        return org, viaje

    def _pedido(self, org):
        return PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )

    def test_permite_peso_valido(self):
        """clean() permite guardar si peso no excede capacidad."""
        org, viaje = self._viaje(Decimal('5000'))
        pedido = self._pedido(org)

        detalle = ViajeDetalle(viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal('1000'))
        detalle.save()

        assert detalle.pk is not None

    def test_rechaza_peso_excesivo(self):
        """clean() lanza ValidationError si peso supera capacidad."""
        org, viaje = self._viaje(Decimal('1000'))
        pedido = self._pedido(org)

        detalle = ViajeDetalle(viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal('5000'))
        with pytest.raises(ValidationError):
            detalle.save()

    def test_acumula_peso_existente(self):
        """clean() suma pesos de detalles previos para validar el total."""
        org, viaje = self._viaje(Decimal('2000'))

        pedido1 = self._pedido(org)
        pedido2 = self._pedido(org)

        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido1, peso_estimado_kg=Decimal('1000'))

        # 1000 + 1500 = 2500 > 2000 → debe rechazar
        detalle2 = ViajeDetalle(viaje=viaje, pedido=pedido2, peso_estimado_kg=Decimal('1500'))
        with pytest.raises(ValidationError):
            detalle2.save()

    def test_permite_agregar_si_no_excede_acumulado(self):
        """clean() permite dos detalles si la suma no supera la capacidad."""
        org, viaje = self._viaje(Decimal('3000'))

        pedido1 = self._pedido(org)
        pedido2 = self._pedido(org)

        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido1, peso_estimado_kg=Decimal('1000'))
        detalle2 = ViajeDetalle(viaje=viaje, pedido=pedido2, peso_estimado_kg=Decimal('1000'))
        detalle2.save()  # 1000 + 1000 = 2000 < 3000 → OK

        assert detalle2.pk is not None

    def test_permite_actualizar_mismo_detalle(self):
        """Al actualizar un detalle existente, no cuenta su propio peso dos veces."""
        org, viaje = self._viaje(Decimal('2000'))
        pedido = self._pedido(org)

        detalle = ViajeDetalle.objects.create(
            viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal('1000')
        )
        # Aumentar a 1500 — sigue dentro de 2000
        detalle.peso_estimado_kg = Decimal('1500')
        detalle.save()

        detalle.refresh_from_db()
        assert detalle.peso_estimado_kg == Decimal('1500')


# ── Viaje.puede_eliminarse ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestViajePuedeEliminarse:

    @pytest.mark.parametrize('estado,esperado', [
        ('Programado', True),
        ('En Ruta',    False),
        ('Completado', False),
        ('Cancelado',  False),
    ])
    def test_estados(self, estado, esperado):
        org = OrganizationFactory()
        viaje = ViajeFactory(
            organization=org,
            vehiculo=VehiculoFactory(organization=org),
            chofer=UserFactory(organization=org),
            estado=estado,
        )
        assert viaje.puede_eliminarse() is esperado


# ── Viaje.peso_total_kg ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestViajePesoTotal:

    def test_peso_total_suma_detalles(self):
        org = OrganizationFactory()
        vehiculo = VehiculoFactory(organization=org, capacidad_kg=Decimal('5000'))
        chofer = UserFactory(organization=org)
        viaje = ViajeFactory(organization=org, vehiculo=vehiculo, chofer=chofer)

        pedido1 = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        pedido2 = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )

        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido1, peso_estimado_kg=Decimal('600'))
        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido2, peso_estimado_kg=Decimal('400'))

        assert viaje.peso_total_kg == Decimal('1000')

    def test_porcentaje_utilizacion(self):
        org = OrganizationFactory()
        vehiculo = VehiculoFactory(organization=org, capacidad_kg=Decimal('2000'))
        chofer = UserFactory(organization=org)
        viaje = ViajeFactory(organization=org, vehiculo=vehiculo, chofer=chofer)

        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        ViajeDetalle.objects.create(viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal('1000'))

        assert viaje.porcentaje_utilizacion == 50.0

    def test_peso_total_sin_detalles_es_cero(self):
        org = OrganizationFactory()
        viaje = ViajeFactory(
            organization=org,
            vehiculo=VehiculoFactory(organization=org),
            chofer=UserFactory(organization=org),
        )
        assert viaje.peso_total_kg == 0
