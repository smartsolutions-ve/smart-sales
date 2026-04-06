"""
Tests Fase 1 — Módulo Pedidos

Cubre:
- PedidoService.guardar_pedido(): creación, numeración por org, validación, totales, IVA
- PedidoService.procesar_descuento_stock(): FEFO, MovimientoInventario, error sin stock
- Pedido.recalcular_total()
- Pedido.puede_eliminarse()
- Aislamiento multi-tenant
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.pedidos.models import Pedido, PedidoItem

from tests.conftest import (
    OrganizationFactory, UserFactory, ClienteFactory, PedidoFactory,
    PedidoItemFactory, CategoriaProductoFactory, ProductoFactory, LoteFactory,
)


# ── PedidoService.guardar_pedido ──────────────────────────────────────────────

@pytest.mark.django_db
class TestGuardarPedido:

    def test_crea_pedido_nuevo(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        cliente = ClienteFactory(organization=org)
        vendedor = UserFactory(organization=org)

        from apps.pedidos.services import PedidoService
        pedido = PedidoService.guardar_pedido(
            organization=org,
            user=user,
            cliente=cliente,
            vendedor=vendedor,
            fecha_pedido=timezone.now().date(),
            items_data=[
                {'producto': 'Prod A', 'sku': '', 'cantidad': Decimal('5'), 'precio': Decimal('100')},
            ],
        )

        assert pedido.pk is not None
        assert pedido.estado == 'Pendiente'
        assert pedido.items.count() == 1

    def test_numeracion_independiente_por_org(self):
        """Cada org comienza su numeración en PED-0001."""
        from apps.pedidos.services import PedidoService
        org1, org2 = OrganizationFactory(), OrganizationFactory()
        items = [{'producto': 'X', 'sku': '', 'cantidad': Decimal('1'), 'precio': Decimal('10')}]

        ped1 = PedidoService.guardar_pedido(
            org1, UserFactory(organization=org1),
            ClienteFactory(organization=org1), UserFactory(organization=org1),
            timezone.now().date(), items,
        )
        ped2 = PedidoService.guardar_pedido(
            org2, UserFactory(organization=org2),
            ClienteFactory(organization=org2), UserFactory(organization=org2),
            timezone.now().date(), items,
        )

        assert ped1.numero == 'PED-0001'
        assert ped2.numero == 'PED-0001'

    def test_rechaza_items_vacios(self):
        from apps.pedidos.services import PedidoService
        org = OrganizationFactory()
        with pytest.raises(ValidationError):
            PedidoService.guardar_pedido(
                org, UserFactory(organization=org),
                ClienteFactory(organization=org), UserFactory(organization=org),
                timezone.now().date(), items_data=[],
            )

    def test_calcula_total_sin_iva(self):
        from apps.pedidos.services import PedidoService
        org = OrganizationFactory()
        pedido = PedidoService.guardar_pedido(
            org, UserFactory(organization=org),
            ClienteFactory(organization=org), UserFactory(organization=org),
            timezone.now().date(),
            items_data=[
                {'producto': 'P1', 'sku': '', 'cantidad': Decimal('10'), 'precio': Decimal('100')},
            ],
        )
        assert pedido.subtotal == Decimal('1000.00')
        assert pedido.monto_iva == Decimal('0.00')
        assert pedido.total == Decimal('1000.00')

    def test_calcula_total_con_iva(self):
        """Producto con exento_iva=False genera IVA del 16%."""
        from apps.pedidos.services import PedidoService
        org = OrganizationFactory()
        cat = CategoriaProductoFactory(organization=org)
        ProductoFactory(organization=org, sku='GRAVA', exento_iva=False, categoria=cat)

        pedido = PedidoService.guardar_pedido(
            org, UserFactory(organization=org),
            ClienteFactory(organization=org), UserFactory(organization=org),
            timezone.now().date(),
            items_data=[
                {'producto': 'Gravado', 'sku': 'GRAVA', 'cantidad': Decimal('100'), 'precio': Decimal('10')},
            ],
        )
        assert pedido.subtotal == Decimal('1000.00')
        assert pedido.monto_iva == Decimal('160.00')
        assert pedido.total == Decimal('1160.00')


# ── PedidoService.procesar_descuento_stock ────────────────────────────────────

@pytest.mark.django_db
class TestDescuentoStock:

    def _setup(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        return org, user

    def test_fefo_descuenta_lote_mas_proximo(self):
        """El lote con fecha_caducidad más cercana se descuenta primero."""
        from apps.pedidos.services import PedidoService
        org, user = self._setup()
        cat = CategoriaProductoFactory(organization=org)
        producto = ProductoFactory(organization=org, sku='FEFO-001', categoria=cat)

        lote_proximo = LoteFactory(
            producto=producto, codigo_lote='L1',
            fecha_caducidad=timezone.now().date() + timezone.timedelta(days=10),
            cantidad_disponible=Decimal('100'),
        )
        lote_lejano = LoteFactory(
            producto=producto, codigo_lote='L2',
            fecha_caducidad=timezone.now().date() + timezone.timedelta(days=60),
            cantidad_disponible=Decimal('100'),
        )

        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        PedidoItem.objects.create(
            pedido=pedido, producto=producto.nombre,
            sku='FEFO-001', cantidad=Decimal('50'), precio=Decimal('10'),
        )

        PedidoService.procesar_descuento_stock(pedido, user)

        lote_proximo.refresh_from_db()
        lote_lejano.refresh_from_db()
        assert lote_proximo.cantidad_disponible == Decimal('50')
        assert lote_lejano.cantidad_disponible == Decimal('100')

    def test_fefo_usa_multiples_lotes_si_necesario(self):
        """Si el primer lote no alcanza, continúa con el siguiente."""
        from apps.pedidos.services import PedidoService
        org, user = self._setup()
        cat = CategoriaProductoFactory(organization=org)
        producto = ProductoFactory(organization=org, sku='FEFO-002', categoria=cat)

        lote1 = LoteFactory(
            producto=producto, codigo_lote='L1',
            fecha_caducidad=timezone.now().date() + timezone.timedelta(days=10),
            cantidad_disponible=Decimal('30'),
        )
        lote2 = LoteFactory(
            producto=producto, codigo_lote='L2',
            fecha_caducidad=timezone.now().date() + timezone.timedelta(days=30),
            cantidad_disponible=Decimal('100'),
        )

        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        PedidoItem.objects.create(
            pedido=pedido, producto=producto.nombre,
            sku='FEFO-002', cantidad=Decimal('80'), precio=Decimal('10'),
        )

        PedidoService.procesar_descuento_stock(pedido, user)

        lote1.refresh_from_db()
        lote2.refresh_from_db()
        assert lote1.cantidad_disponible == Decimal('0')
        assert lote2.cantidad_disponible == Decimal('50')

    def test_crea_movimiento_salida(self):
        """Descuento genera MovimientoInventario tipo SALIDA."""
        from apps.pedidos.services import PedidoService
        from apps.productos.models import MovimientoInventario
        org, user = self._setup()
        cat = CategoriaProductoFactory(organization=org)
        producto = ProductoFactory(organization=org, sku='MOV-001', categoria=cat)
        LoteFactory(producto=producto, cantidad_disponible=Decimal('500'))

        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        PedidoItem.objects.create(
            pedido=pedido, producto=producto.nombre,
            sku='MOV-001', cantidad=Decimal('100'), precio=Decimal('10'),
        )

        PedidoService.procesar_descuento_stock(pedido, user)

        mov = MovimientoInventario.objects.filter(tipo='SALIDA').latest('created_at')
        assert mov.cantidad == Decimal('-100')
        assert pedido.numero in mov.referencia

    def test_lanza_error_sin_stock_suficiente(self):
        """ValidationError si la cantidad pedida supera el stock total."""
        from apps.pedidos.services import PedidoService
        org, user = self._setup()
        cat = CategoriaProductoFactory(organization=org)
        producto = ProductoFactory(organization=org, sku='SIN-001', categoria=cat)
        LoteFactory(producto=producto, cantidad_disponible=Decimal('10'))

        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        PedidoItem.objects.create(
            pedido=pedido, producto=producto.nombre,
            sku='SIN-001', cantidad=Decimal('999'), precio=Decimal('10'),
        )

        with pytest.raises(ValidationError):
            PedidoService.procesar_descuento_stock(pedido, user)

    def test_items_sin_sku_no_generan_movimiento(self):
        """Items sin SKU son ignorados silenciosamente."""
        from apps.pedidos.services import PedidoService
        from apps.productos.models import MovimientoInventario
        org, user = self._setup()

        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        PedidoItem.objects.create(
            pedido=pedido, producto='Sin SKU', sku='',
            cantidad=Decimal('5'), precio=Decimal('10'),
        )

        antes = MovimientoInventario.objects.count()
        PedidoService.procesar_descuento_stock(pedido, user)
        assert MovimientoInventario.objects.count() == antes


# ── Pedido.recalcular_total ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestRecalcularTotal:

    def test_suma_correctamente(self):
        org = OrganizationFactory()
        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        PedidoItem.objects.create(pedido=pedido, producto='A', cantidad=Decimal('5'), precio=Decimal('100'))
        PedidoItem.objects.create(pedido=pedido, producto='B', cantidad=Decimal('3'), precio=Decimal('50'))

        pedido.recalcular_total()

        assert pedido.subtotal == Decimal('650.00')
        assert pedido.total == Decimal('650.00')

    def test_sin_items_total_cero(self):
        org = OrganizationFactory()
        pedido = PedidoFactory(
            organization=org,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        pedido.recalcular_total()
        assert pedido.subtotal == Decimal('0.00')
        assert pedido.total == Decimal('0.00')


# ── Pedido.puede_eliminarse ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestPuedeEliminarse:

    @pytest.mark.parametrize('estado,esperado', [
        ('Pendiente', True),
        ('Confirmado', False),
        ('En Proceso', False),
        ('Entregado', False),
        ('Cancelado', False),
    ])
    def test_estados(self, estado, esperado):
        org = OrganizationFactory()
        pedido = PedidoFactory(
            organization=org, estado=estado,
            cliente=ClienteFactory(organization=org),
            vendedor=UserFactory(organization=org),
        )
        assert pedido.puede_eliminarse() is esperado


# ── Aislamiento multi-tenant ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestTenantIsolation:

    def test_org_a_no_ve_pedidos_de_org_b(self):
        org_a, org_b = OrganizationFactory(), OrganizationFactory()

        ped_a = PedidoFactory(
            organization=org_a,
            cliente=ClienteFactory(organization=org_a),
            vendedor=UserFactory(organization=org_a),
        )
        ped_b = PedidoFactory(
            organization=org_b,
            cliente=ClienteFactory(organization=org_b),
            vendedor=UserFactory(organization=org_b),
        )

        qs_a = Pedido.objects.filter(organization=org_a)
        assert qs_a.filter(pk=ped_a.pk).exists()
        assert not qs_a.filter(pk=ped_b.pk).exists()

    def test_cliente_org_a_no_visible_en_org_b(self):
        from apps.pedidos.models import Cliente
        org_a, org_b = OrganizationFactory(), OrganizationFactory()

        cli_a = ClienteFactory(organization=org_a)
        cli_b = ClienteFactory(organization=org_b)

        assert not Cliente.objects.filter(organization=org_b, pk=cli_a.pk).exists()
        assert not Cliente.objects.filter(organization=org_a, pk=cli_b.pk).exists()
