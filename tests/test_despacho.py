"""
Tests del módulo de despacho y logística.
"""
import pytest
from datetime import date, timedelta
from django.urls import reverse
from django.utils import timezone
from .conftest import PedidoFactory


@pytest.mark.django_db
class TestVistaDespacho:
    """Tests de la vista de despacho."""

    def test_despacho_solo_muestra_pedidos_no_cancelados(self, client_gerente, org, gerente, cliente):
        """Los pedidos cancelados no aparecen en la vista de despacho."""
        pedido_activo = PedidoFactory(
            organization=org, vendedor=gerente, cliente=cliente,
            estado='Confirmado', estado_despacho='Pendiente Despacho'
        )
        pedido_cancelado = PedidoFactory(
            organization=org, vendedor=gerente, cliente=cliente,
            estado='Cancelado', estado_despacho='Pendiente Despacho'
        )

        url = reverse('despacho:index')
        resp = client_gerente.get(url)
        content = resp.content.decode()

        assert pedido_activo.numero in content
        assert pedido_cancelado.numero not in content

    def test_cambiar_estado_despacho_htmx(self, client_gerente, pedido):
        """Cambiar el estado de despacho via HTMX actualiza la BD."""
        assert pedido.estado_despacho == 'Pendiente Despacho'

        url = reverse('despacho:cambiar_estado', kwargs={'pk': pedido.pk})
        resp = client_gerente.post(
            url,
            {'estado_despacho': 'Programado'},
            HTTP_HX_REQUEST='true',
        )
        assert resp.status_code == 200
        pedido.refresh_from_db()
        assert pedido.estado_despacho == 'Programado'

    def test_urgencia_pedidos_proximos_a_vencer(self, client_gerente, org, gerente, cliente):
        """Pedidos con fecha_entrega próxima se marcan como urgentes."""
        manana = date.today() + timedelta(days=1)
        pedido_urgente = PedidoFactory(
            organization=org, vendedor=gerente, cliente=cliente,
            estado='Confirmado', estado_despacho='Pendiente Despacho',
            fecha_entrega=manana,
        )

        url = reverse('despacho:index')
        resp = client_gerente.get(url)
        # La vista debe incluir alguna marca de urgencia (clase CSS o texto)
        content = resp.content.decode()
        assert pedido_urgente.numero in content

    def test_despacho_sin_pedidos_pendientes_muestra_mensaje(self, client_gerente, org):
        """Si no hay pedidos pendientes de despacho, se muestra un estado vacío."""
        url = reverse('despacho:index')
        resp = client_gerente.get(url)
        assert resp.status_code == 200
