"""
Tests del módulo de inteligencia de competencia.
"""
import pytest
from decimal import Decimal
from django.urls import reverse
from .conftest import CompetenciaRegistroFactory, OrganizationFactory


@pytest.mark.django_db
class TestCompetenciaRegistro:
    """Tests del modelo CompetenciaRegistro."""

    def test_diferencia_precio_positiva_somos_mas_caros(self, org, gerente):
        """Si nuestro precio > precio competidor, la diferencia es positiva."""
        registro = CompetenciaRegistroFactory(
            organization=org,
            vendedor=gerente,
            precio_comp=Decimal('100.00'),
            precio_nuestro=Decimal('120.00'),
        )
        assert registro.diferencia_precio == Decimal('20.00')
        assert registro.somos_mas_caros is True

    def test_diferencia_precio_negativa_somos_mas_baratos(self, org, gerente):
        """Si nuestro precio < precio competidor, la diferencia es negativa."""
        registro = CompetenciaRegistroFactory(
            organization=org,
            vendedor=gerente,
            precio_comp=Decimal('120.00'),
            precio_nuestro=Decimal('100.00'),
        )
        assert registro.diferencia_precio == Decimal('-20.00')
        assert registro.somos_mas_caros is False

    def test_diferencia_precio_sin_precios_es_none(self, org, gerente):
        """Sin precios cargados, la diferencia es None."""
        registro = CompetenciaRegistroFactory(
            organization=org,
            vendedor=gerente,
            precio_comp=None,
            precio_nuestro=None,
        )
        assert registro.diferencia_precio is None

    def test_lista_competencia_solo_muestra_org_propia(self, client_gerente, org, gerente):
        """La lista solo muestra registros de la organización del usuario."""
        reg_propio = CompetenciaRegistroFactory(organization=org, vendedor=gerente)
        otra_org = OrganizationFactory()
        reg_ajeno = CompetenciaRegistroFactory(
            organization=otra_org,
            vendedor=gerente,  # mismo vendedor, otra org
        )

        url = reverse('competencia:lista')
        resp = client_gerente.get(url)
        content = resp.content.decode()

        assert reg_propio.competidor in content
        assert reg_ajeno.competidor not in content

    def test_vendedor_puede_registrar_competencia_desde_campo(self, client_vendedor, org, vendedor, cliente):
        """Un vendedor puede crear registros de competencia desde el campo."""
        url = reverse('campo:competencia_nueva')
        resp = client_vendedor.post(url, {
            'fecha': '2026-03-10',
            'producto': 'Aceite El Turpial 1L',
            'competidor': 'Aceite XYZ',
            'precio_comp': '5.50',
            'precio_nuestro': '6.00',
            'accion_tomada': 'Se ofreció descuento del 5%',
        })
        assert resp.status_code == 302  # Redirige al campo

        from apps.competencia.models import CompetenciaRegistro
        assert CompetenciaRegistro.objects.filter(
            organization=org,
            vendedor=vendedor,
        ).exists()
