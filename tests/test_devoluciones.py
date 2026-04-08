"""
Tests del módulo de Devoluciones y Notas de Crédito.

Cubre:
- Creación y cálculo de monto
- Flujo de estados (aprobar, completar, rechazar)
- Reingreso de inventario al completar
- Aislamiento de tenant
- Vistas HTTP (lista, detalle, crear, aprobar, completar, rechazar)
"""
import pytest
from decimal import Decimal

import factory
from django.urls import reverse
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.devoluciones.models import Devolucion, DevolucionItem

from .conftest import (
    ClienteFactory,
    LoteFactory,
    OrganizationFactory,
    PedidoFactory,
    PedidoItemFactory,
    ProductoFactory,
    UserFactory,
    CategoriaProductoFactory,
)


# ── Factories ──────────────────────────────────────────────────────────────────

class DevolucionFactory(DjangoModelFactory):
    class Meta:
        model = 'devoluciones.Devolucion'

    organization = factory.SubFactory(OrganizationFactory)
    pedido = factory.SubFactory(PedidoFactory)
    cliente = factory.SubFactory(ClienteFactory)
    fecha = factory.LazyFunction(lambda: timezone.now().date())
    motivo = 'DEFECTO'
    estado = 'Pendiente'
    observaciones = ''
    monto_credito = Decimal('0.00')
    reingresar_inventario = True
    registrado_por = factory.SubFactory(UserFactory)


class DevolucionItemFactory(DjangoModelFactory):
    class Meta:
        model = 'devoluciones.DevolucionItem'

    organization = factory.LazyAttribute(lambda o: o.devolucion.organization)
    devolucion = factory.SubFactory(DevolucionFactory)
    producto = 'Producto de prueba'
    sku = 'SKU-TEST'
    cantidad = Decimal('5.00')
    precio_unitario = Decimal('100.00')


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def org():
    return OrganizationFactory()


@pytest.fixture
def gerente(org):
    return UserFactory(organization=org, role='gerente')


@pytest.fixture
def cliente(org):
    return ClienteFactory(organization=org)


@pytest.fixture
def pedido(org, gerente, cliente):
    return PedidoFactory(organization=org, vendedor=gerente, cliente=cliente)


@pytest.fixture
def devolucion(org, gerente, pedido, cliente):
    return DevolucionFactory(
        organization=org,
        pedido=pedido,
        cliente=cliente,
        registrado_por=gerente,
    )


@pytest.fixture
def devolucion_con_items(devolucion):
    """Devolución con ítems y monto calculado."""
    DevolucionItemFactory(
        devolucion=devolucion,
        organization=devolucion.organization,
        cantidad=Decimal('3'),
        precio_unitario=Decimal('100'),
    )
    DevolucionItemFactory(
        devolucion=devolucion,
        organization=devolucion.organization,
        cantidad=Decimal('2'),
        precio_unitario=Decimal('50'),
    )
    devolucion.calcular_monto()
    devolucion.refresh_from_db()
    return devolucion


@pytest.fixture
def client_gerente(client, gerente):
    client.force_login(gerente)
    return client


# ── Tests de modelo ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDevolucionModelo:
    """Tests de los métodos del modelo Devolucion."""

    def test_str_repr(self, devolucion):
        """La representación incluye el pk, cliente y fecha."""
        resultado = str(devolucion)
        assert f'DEV-{devolucion.pk}' in resultado
        assert str(devolucion.fecha) in resultado

    def test_puede_aprobar_solo_pendiente(self, devolucion):
        """Solo las devoluciones en estado Pendiente pueden aprobarse."""
        assert devolucion.puede_aprobar() is True
        devolucion.estado = 'Aprobada'
        assert devolucion.puede_aprobar() is False

    def test_puede_completar_solo_aprobada(self, devolucion):
        """Solo las devoluciones Aprobadas pueden completarse."""
        assert devolucion.puede_completar() is False
        devolucion.estado = 'Aprobada'
        assert devolucion.puede_completar() is True

    def test_puede_rechazar_solo_pendiente(self, devolucion):
        """Solo las devoluciones Pendientes pueden rechazarse."""
        assert devolucion.puede_rechazar() is True
        devolucion.estado = 'Rechazada'
        assert devolucion.puede_rechazar() is False

    def test_calcular_monto_suma_items(self, devolucion_con_items):
        """calcular_monto() suma cantidad × precio de todos los ítems."""
        # 3 × 100 + 2 × 50 = 400
        assert devolucion_con_items.monto_credito == Decimal('400.00')

    def test_calcular_monto_sin_items_es_cero(self, devolucion):
        """calcular_monto() retorna 0 si no hay ítems."""
        resultado = devolucion.calcular_monto()
        assert resultado == 0

    def test_devolucion_item_subtotal(self, devolucion):
        """La propiedad subtotal es cantidad × precio_unitario."""
        item = DevolucionItemFactory(
            devolucion=devolucion,
            organization=devolucion.organization,
            cantidad=Decimal('4'),
            precio_unitario=Decimal('25'),
        )
        assert item.subtotal == Decimal('100.00')

    def test_item_hereda_organization_de_devolucion(self, devolucion):
        """El item hereda la organización de la devolución al guardar."""
        item = DevolucionItem(
            devolucion=devolucion,
            producto='Prueba',
            cantidad=Decimal('1'),
            precio_unitario=Decimal('10'),
        )
        item.save()
        assert item.organization == devolucion.organization


# ── Tests de flujo de estados ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestDevolucionFlujo:
    """Tests del ciclo de vida de una devolución."""

    def test_aprobar_registra_usuario(self, devolucion, gerente):
        """Al aprobar, aprobado_por queda registrado y el estado cambia."""
        devolucion.estado = 'Aprobada'
        devolucion.aprobado_por = gerente
        devolucion.save(update_fields=['estado', 'aprobado_por', 'updated_at'])
        devolucion.refresh_from_db()
        assert devolucion.aprobado_por == gerente
        assert devolucion.estado == 'Aprobada'

    def test_no_completar_sin_aprobar(self, devolucion):
        """Una devolución Pendiente no puede completarse."""
        assert devolucion.puede_completar() is False

    def test_completar_reingresa_inventario(self, org, gerente, pedido, cliente):
        """Al completar con reingresar=True, se crean Lote y MovimientoInventario."""
        from apps.productos.models import Lote, MovimientoInventario

        # Crear producto con SKU en la misma org
        cat = CategoriaProductoFactory(organization=org)
        producto = ProductoFactory(organization=org, sku='SKU-DEV-001', categoria=cat)

        dev = DevolucionFactory(
            organization=org,
            pedido=pedido,
            cliente=cliente,
            registrado_por=gerente,
            estado='Aprobada',
            reingresar_inventario=True,
        )
        DevolucionItemFactory(
            devolucion=dev,
            organization=org,
            sku='SKU-DEV-001',
            cantidad=Decimal('10'),
            precio_unitario=Decimal('50'),
        )

        # Ejecutar lógica de reingreso directamente desde el módulo de vistas
        from apps.devoluciones.views import _reingresar_inventario
        _reingresar_inventario(dev, org, gerente)

        item = dev.items.first()
        item.refresh_from_db()

        assert item.lote_reingreso is not None
        assert item.lote_reingreso.cantidad_disponible == Decimal('10')

        mov = MovimientoInventario.objects.filter(
            lote=item.lote_reingreso, tipo='ENTRADA'
        ).first()
        assert mov is not None
        assert mov.cantidad == Decimal('10')

    def test_sku_desconocido_no_crea_lote(self, org, gerente, pedido, cliente):
        """Un ítem cuyo SKU no existe en el catálogo se omite en el reingreso."""
        from apps.productos.models import Lote

        lotes_antes = Lote.objects.filter(organization=org).count()

        dev = DevolucionFactory(
            organization=org,
            pedido=pedido,
            cliente=cliente,
            registrado_por=gerente,
            estado='Aprobada',
        )
        DevolucionItemFactory(
            devolucion=dev,
            organization=org,
            sku='SKU-NO-EXISTE-XYZ',
            cantidad=Decimal('5'),
            precio_unitario=Decimal('20'),
        )

        from apps.devoluciones.views import _reingresar_inventario
        _reingresar_inventario(dev, org, gerente)

        assert Lote.objects.filter(organization=org).count() == lotes_antes

    def test_aislamiento_tenant(self, org, gerente, pedido, cliente):
        """Una organización no puede ver las devoluciones de otra organización."""
        org2 = OrganizationFactory()
        cliente2 = ClienteFactory(organization=org2)
        pedido2 = PedidoFactory(organization=org2, cliente=cliente2)
        gerente2 = UserFactory(organization=org2, role='gerente')

        dev_org1 = DevolucionFactory(
            organization=org,
            pedido=pedido,
            cliente=cliente,
            registrado_por=gerente,
        )
        DevolucionFactory(
            organization=org2,
            pedido=pedido2,
            cliente=cliente2,
            registrado_por=gerente2,
        )

        resultado = Devolucion.objects.filter(organization=org)
        assert resultado.count() == 1
        assert resultado.first().pk == dev_org1.pk


# ── Tests de vistas HTTP ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDevolucionVistas:
    """Tests de las vistas HTTP del módulo."""

    def test_lista_requiere_autenticacion(self, client):
        """La lista redirige a login si el usuario no está autenticado."""
        url = reverse('devoluciones:lista')
        resp = client.get(url)
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_lista_muestra_devoluciones_de_org(self, client_gerente, devolucion_con_items):
        """La lista muestra las devoluciones de la organización del usuario."""
        url = reverse('devoluciones:lista')
        resp = client_gerente.get(url)
        assert resp.status_code == 200
        assert devolucion_con_items in resp.context['devoluciones']

    def test_detalle_devolucion(self, client_gerente, devolucion_con_items):
        """El detalle muestra la devolución y sus ítems."""
        url = reverse('devoluciones:detalle', kwargs={'pk': devolucion_con_items.pk})
        resp = client_gerente.get(url)
        assert resp.status_code == 200
        assert resp.context['devolucion'] == devolucion_con_items

    def test_detalle_otra_org_devuelve_404(self, client_gerente):
        """No se puede acceder al detalle de una devolución de otra organización."""
        org2 = OrganizationFactory()
        cliente2 = ClienteFactory(organization=org2)
        pedido2 = PedidoFactory(organization=org2, cliente=cliente2)
        gerente2 = UserFactory(organization=org2, role='gerente')
        dev_otra_org = DevolucionFactory(
            organization=org2,
            pedido=pedido2,
            cliente=cliente2,
            registrado_por=gerente2,
        )
        url = reverse('devoluciones:detalle', kwargs={'pk': dev_otra_org.pk})
        resp = client_gerente.get(url)
        assert resp.status_code == 404

    def test_aprobar_via_post(self, client_gerente, devolucion, gerente):
        """POST a aprobar cambia el estado a Aprobada y registra el usuario."""
        url = reverse('devoluciones:aprobar', kwargs={'pk': devolucion.pk})
        resp = client_gerente.post(url)
        devolucion.refresh_from_db()
        assert resp.status_code == 302
        assert devolucion.estado == 'Aprobada'
        assert devolucion.aprobado_por == gerente

    def test_aprobar_devolucion_ya_aprobada_falla(self, client_gerente, devolucion, gerente):
        """No se puede aprobar una devolución que ya está aprobada."""
        devolucion.estado = 'Aprobada'
        devolucion.aprobado_por = gerente
        devolucion.save()

        url = reverse('devoluciones:aprobar', kwargs={'pk': devolucion.pk})
        resp = client_gerente.post(url)
        devolucion.refresh_from_db()
        # El estado no cambia y redirige de vuelta al detalle
        assert resp.status_code == 302
        assert devolucion.estado == 'Aprobada'

    def test_rechazar_requiere_observaciones(self, client_gerente, devolucion):
        """POST a rechazar sin observaciones no cambia el estado."""
        url = reverse('devoluciones:rechazar', kwargs={'pk': devolucion.pk})
        resp = client_gerente.post(url, {'observaciones': ''})
        devolucion.refresh_from_db()
        assert devolucion.estado == 'Pendiente'

    def test_rechazar_con_observaciones(self, client_gerente, devolucion):
        """POST a rechazar con observaciones cambia el estado a Rechazada."""
        url = reverse('devoluciones:rechazar', kwargs={'pk': devolucion.pk})
        resp = client_gerente.post(url, {'observaciones': 'Producto en buen estado'})
        devolucion.refresh_from_db()
        assert resp.status_code == 302
        assert devolucion.estado == 'Rechazada'
        assert devolucion.observaciones == 'Producto en buen estado'

    def test_completar_cambia_estado(self, client_gerente, devolucion, gerente):
        """POST a completar una devolución aprobada cambia el estado a Completada."""
        devolucion.estado = 'Aprobada'
        devolucion.aprobado_por = gerente
        devolucion.save()

        url = reverse('devoluciones:completar', kwargs={'pk': devolucion.pk})
        resp = client_gerente.post(url, {'reingresar_inventario': 'on'})
        devolucion.refresh_from_db()
        assert resp.status_code == 302
        assert devolucion.estado == 'Completada'

    def test_completar_pendiente_falla(self, client_gerente, devolucion):
        """No se puede completar una devolución que sigue en Pendiente."""
        url = reverse('devoluciones:completar', kwargs={'pk': devolucion.pk})
        resp = client_gerente.post(url)
        devolucion.refresh_from_db()
        assert devolucion.estado == 'Pendiente'

    def test_pedido_items_json(self, client_gerente, pedido):
        """El endpoint JSON devuelve los ítems del pedido."""
        PedidoItemFactory(pedido=pedido, cantidad=Decimal('5'), precio=Decimal('100'))
        url = reverse('devoluciones:pedido_items', kwargs={'pedido_pk': pedido.pk})
        resp = client_gerente.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert 'items' in data
        assert len(data['items']) == 1

    def test_pedido_items_json_otra_org_404(self, client_gerente):
        """El endpoint JSON protege contra accesos cross-tenant."""
        org2 = OrganizationFactory()
        cliente2 = ClienteFactory(organization=org2)
        pedido2 = PedidoFactory(organization=org2, cliente=cliente2)
        url = reverse('devoluciones:pedido_items', kwargs={'pedido_pk': pedido2.pk})
        resp = client_gerente.get(url)
        assert resp.status_code == 404

    def test_crear_get(self, client_gerente):
        """GET a crear muestra el formulario."""
        url = reverse('devoluciones:crear')
        resp = client_gerente.get(url)
        assert resp.status_code == 200
        assert 'motivos' in resp.context

    def test_crear_post_sin_items_falla(self, client_gerente, pedido, cliente):
        """POST a crear sin ítems no crea la devolución."""
        url = reverse('devoluciones:crear')
        data = {
            'pedido': pedido.pk,
            'cliente': cliente.pk,
            'motivo': 'DEFECTO',
            'fecha': '2026-04-07',
        }
        resp = client_gerente.post(url, data)
        # Retorna el form con error, no redirige
        assert resp.status_code == 200
        assert Devolucion.objects.filter(organization=pedido.organization).count() == 0

    def test_crear_post_con_items(self, client_gerente, org, pedido, cliente, gerente):
        """POST a crear con ítems válidos crea la devolución correctamente."""
        url = reverse('devoluciones:crear')
        data = {
            'pedido': pedido.pk,
            'cliente': cliente.pk,
            'motivo': 'DEFECTO',
            'fecha': '2026-04-07',
            'item_producto_0': 'Producto A',
            'item_sku_0': 'SKU-001',
            'item_cantidad_0': '3',
            'item_precio_0': '100',
        }
        resp = client_gerente.post(url, data)
        assert resp.status_code == 302
        dev = Devolucion.objects.filter(organization=org).first()
        assert dev is not None
        assert dev.estado == 'Pendiente'
        assert dev.items.count() == 1
        assert dev.monto_credito == Decimal('300.00')
