"""
Tests del módulo de pedidos:
- CRUD de pedidos
- Cálculo automático de totales (signals)
- Numeración por organización
- Cambios de estado
- Items del pedido
"""
import pytest
from decimal import Decimal
from django.urls import reverse
from apps.pedidos.models import Pedido, PedidoItem, Cliente
from apps.pedidos.utils import generar_numero_pedido
from .conftest import (
    PedidoFactory, PedidoItemFactory, ClienteFactory,
    OrganizationFactory, UserFactory,
)


@pytest.mark.django_db
class TestTotalPedido:
    """Tests del cálculo automático de totales via signals."""

    def test_total_se_calcula_al_agregar_item(self, pedido):
        """Al agregar un ítem, el total del pedido se actualiza."""
        PedidoItemFactory(pedido=pedido, cantidad=Decimal('5'), precio=Decimal('100'))
        pedido.refresh_from_db()
        assert pedido.total == Decimal('500.00')

    def test_total_acumula_multiples_items(self, pedido):
        """Varios ítems se suman correctamente."""
        PedidoItemFactory(pedido=pedido, cantidad=Decimal('2'), precio=Decimal('100'))
        PedidoItemFactory(pedido=pedido, cantidad=Decimal('3'), precio=Decimal('50'))
        pedido.refresh_from_db()
        # 2*100 + 3*50 = 200 + 150 = 350
        assert pedido.total == Decimal('350.00')

    def test_total_se_recalcula_al_eliminar_item(self, pedido):
        """Al eliminar un ítem, el total se reduce."""
        item1 = PedidoItemFactory(pedido=pedido, cantidad=Decimal('2'), precio=Decimal('100'))
        item2 = PedidoItemFactory(pedido=pedido, cantidad=Decimal('1'), precio=Decimal('50'))
        pedido.refresh_from_db()
        assert pedido.total == Decimal('250.00')

        item2.delete()
        pedido.refresh_from_db()
        assert pedido.total == Decimal('200.00')

    def test_total_cero_sin_items(self, pedido):
        """Un pedido sin ítems tiene total 0."""
        pedido.refresh_from_db()
        assert pedido.total == Decimal('0.00')

    def test_subtotal_item_es_property(self, pedido):
        """El subtotal del ítem es una propiedad calculada (no columna de BD)."""
        item = PedidoItemFactory(pedido=pedido, cantidad=Decimal('4'), precio=Decimal('25'))
        assert item.subtotal == Decimal('100.00')


@pytest.mark.django_db
class TestNumeracionPedidos:
    """Tests de la numeración correlativa PED-XXXX por organización."""

    def test_primer_pedido_es_ped_0001(self, org):
        numero = generar_numero_pedido(org)
        assert numero == 'PED-0001'

    def test_segundo_pedido_es_ped_0002(self, org):
        PedidoFactory(organization=org, numero='PED-0001')
        numero = generar_numero_pedido(org)
        assert numero == 'PED-0002'

    def test_numeracion_independiente_por_org(self, org):
        """Dos organizaciones distintas tienen numeración independiente."""
        otra_org = OrganizationFactory()
        PedidoFactory(organization=otra_org, numero='PED-0001')
        PedidoFactory(organization=otra_org, numero='PED-0002')

        # La organización `org` empieza desde cero
        numero = generar_numero_pedido(org)
        assert numero == 'PED-0001'

    def test_formato_cuatro_digitos(self, org):
        """El número siempre tiene 4 dígitos con ceros a la izquierda."""
        for i in range(1, 10):
            PedidoFactory(organization=org, numero=f'PED-{i:04d}')
        numero = generar_numero_pedido(org)
        assert numero == 'PED-0010'


@pytest.mark.django_db
class TestEstadosPedido:
    """Tests de cambios de estado del pedido."""

    def test_estado_inicial_es_pendiente(self, pedido):
        assert pedido.estado == 'Pendiente'

    def test_puede_cambiar_estado_pendiente(self, pedido):
        assert pedido.puede_cambiar_estado() is True

    def test_no_puede_cambiar_estado_entregado(self, pedido):
        pedido.estado = 'Entregado'
        pedido.save()
        assert pedido.puede_cambiar_estado() is False

    def test_no_puede_cambiar_estado_cancelado(self, pedido):
        pedido.estado = 'Cancelado'
        pedido.save()
        assert pedido.puede_cambiar_estado() is False

    def test_puede_eliminar_solo_pendiente(self, pedido):
        assert pedido.puede_eliminarse() is True

        pedido.estado = 'Confirmado'
        pedido.save()
        assert pedido.puede_eliminarse() is False

    def test_cambiar_estado_via_view_htmx(self, client_gerente, pedido):
        """El endpoint de cambio de estado devuelve HTML parcial (HTMX)."""
        url = reverse('pedidos:cambiar_estado', kwargs={'pk': pedido.pk})
        resp = client_gerente.post(
            url,
            {'estado': 'Confirmado'},
            HTTP_HX_REQUEST='true',
        )
        assert resp.status_code == 200
        pedido.refresh_from_db()
        assert pedido.estado == 'Confirmado'

    def test_no_cambiar_estado_pedido_entregado(self, client_gerente, pedido):
        """No se puede cambiar el estado de un pedido en estado terminal."""
        pedido.estado = 'Entregado'
        pedido.save()

        url = reverse('pedidos:cambiar_estado', kwargs={'pk': pedido.pk})
        resp = client_gerente.post(url, {'estado': 'Pendiente'})
        assert resp.status_code in (400, 302)
        pedido.refresh_from_db()
        assert pedido.estado == 'Entregado'  # No cambió


@pytest.mark.django_db
class TestCRUDPedidos:
    """Tests de creación, edición y eliminación de pedidos."""

    def test_crear_pedido_requiere_autenticacion(self, client, org, cliente):
        url = reverse('pedidos:crear')
        resp = client.get(url)
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_crear_pedido_asigna_numero_automatico(self, client_gerente, org, cliente, gerente):
        url = reverse('pedidos:crear')
        resp = client_gerente.post(url, {
            'fecha_pedido': '2026-03-10',
            'cliente': cliente.pk,
            'vendedor': gerente.pk,
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-0-producto': 'Aceite El Turpial',
            'items-0-cantidad': '10',
            'items-0-precio': '5.50',
        })
        # Debe redirigir a la lista tras crear
        assert resp.status_code == 302
        pedido = Pedido.objects.filter(organization=org).first()
        assert pedido is not None
        assert pedido.numero.startswith('PED-')

    def test_eliminar_pedido_pendiente(self, client_gerente, pedido):
        """Un pedido en estado Pendiente puede eliminarse."""
        assert pedido.estado == 'Pendiente'
        url = reverse('pedidos:eliminar', kwargs={'pk': pedido.pk})
        resp = client_gerente.post(url)
        assert resp.status_code == 302
        assert not Pedido.objects.filter(pk=pedido.pk).exists()

    def test_no_eliminar_pedido_confirmado(self, client_gerente, pedido):
        """Un pedido confirmado no puede eliminarse, solo cancelarse."""
        pedido.estado = 'Confirmado'
        pedido.save()

        url = reverse('pedidos:eliminar', kwargs={'pk': pedido.pk})
        resp = client_gerente.post(url)
        # Debe devolver error, no eliminar
        assert Pedido.objects.filter(pk=pedido.pk).exists()


@pytest.mark.django_db
class TestClientes:
    """Tests del modelo Cliente."""

    def test_cliente_no_eliminable_con_pedidos(self, cliente, pedido):
        """Un cliente con pedidos no puede eliminarse."""
        assert not cliente.puede_eliminarse()

    def test_cliente_eliminable_sin_pedidos(self, cliente):
        """Un cliente sin pedidos puede eliminarse."""
        assert cliente.puede_eliminarse()

    def test_nombre_unico_por_org(self, org):
        """Dos clientes de la misma organización no pueden tener el mismo nombre."""
        from django.db import IntegrityError
        ClienteFactory(organization=org, nombre='Bodega El Palmar')
        with pytest.raises(IntegrityError):
            ClienteFactory(organization=org, nombre='Bodega El Palmar')

    def test_nombre_repetido_en_otra_org_es_valido(self, org):
        """El mismo nombre de cliente en distintas organizaciones es válido."""
        otra_org = OrganizationFactory()
        ClienteFactory(organization=org, nombre='Bodega El Palmar')
        # No debe lanzar error
        ClienteFactory(organization=otra_org, nombre='Bodega El Palmar')
        assert Cliente.objects.filter(nombre='Bodega El Palmar').count() == 2
