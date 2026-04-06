"""
Fixtures globales para pytest-django.
Todas las factories y fixtures base del proyecto.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker('es')


# ── Factories ──────────────────────────────────────────────────────────────────

class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = 'accounts.Organization'

    name      = factory.LazyFunction(lambda: fake.company())
    slug      = factory.LazyAttribute(lambda o: o.name.lower().replace(' ', '-')[:50])
    is_active = True
    plan      = 'starter'


class UserFactory(DjangoModelFactory):
    class Meta:
        model = 'accounts.User'

    username     = factory.LazyFunction(lambda: fake.user_name())
    email        = factory.LazyFunction(lambda: fake.email())
    first_name   = factory.LazyFunction(lambda: fake.first_name())
    last_name    = factory.LazyFunction(lambda: fake.last_name())
    password     = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active    = True
    organization = factory.SubFactory(OrganizationFactory)
    role         = 'gerente'


class VendedorFactory(UserFactory):
    role = 'vendedor'


class SuperadminFactory(UserFactory):
    role         = 'superadmin'
    organization = None


class ClienteFactory(DjangoModelFactory):
    class Meta:
        model = 'pedidos.Cliente'

    organization = factory.SubFactory(OrganizationFactory)
    nombre       = factory.LazyFunction(lambda: fake.company())
    contacto     = factory.LazyFunction(lambda: fake.name())
    telefono     = factory.LazyFunction(lambda: fake.phone_number())
    email        = factory.LazyFunction(lambda: fake.email())


class PedidoFactory(DjangoModelFactory):
    class Meta:
        model = 'pedidos.Pedido'

    organization    = factory.SubFactory(OrganizationFactory)
    numero          = factory.Sequence(lambda n: f'PED-{n+1:04d}')
    fecha_pedido    = factory.LazyFunction(lambda: timezone.now().date())
    cliente         = factory.SubFactory(ClienteFactory)
    vendedor        = factory.SubFactory(UserFactory)
    estado          = 'Pendiente'
    estado_despacho = 'Pendiente Despacho'
    total           = Decimal('0.00')


class PedidoItemFactory(DjangoModelFactory):
    class Meta:
        model = 'pedidos.PedidoItem'

    pedido   = factory.SubFactory(PedidoFactory)
    producto = factory.LazyFunction(lambda: fake.bs().title()[:100])
    cantidad = Decimal('10.00')
    precio   = Decimal('50.00')


class FacturaFactory(DjangoModelFactory):
    class Meta:
        model = 'pedidos.Factura'

    pedido          = factory.SubFactory(PedidoFactory)
    numero_factura  = factory.Sequence(lambda n: f'FAC-{n+1:04d}')
    fecha_factura   = factory.LazyFunction(lambda: timezone.now().date())
    monto           = Decimal('500.00')
    observaciones   = ''


class VehiculoFactory(DjangoModelFactory):
    class Meta:
        model = 'flotas.Vehiculo'

    organization   = factory.SubFactory(OrganizationFactory)
    placa          = factory.Sequence(lambda n: f'ABC-{n+1:03d}')
    marca          = 'Ford'
    modelo         = 'F-350'
    capacidad_kg   = Decimal('5000.00')
    is_active      = True


class ViajeFactory(DjangoModelFactory):
    class Meta:
        model = 'flotas.Viaje'

    organization   = factory.SubFactory(OrganizationFactory)
    vehiculo       = factory.SubFactory(VehiculoFactory)
    chofer         = factory.SubFactory(UserFactory)
    fecha          = factory.LazyFunction(lambda: timezone.now().date())
    estado         = 'Programado'


class ZonaFactory(DjangoModelFactory):
    class Meta:
        model = 'cuotas.Zona'

    organization   = factory.SubFactory(OrganizationFactory)
    nombre         = factory.LazyFunction(lambda: fake.city())


class VentaMensualFactory(DjangoModelFactory):
    class Meta:
        model = 'cuotas.VentaMensual'

    organization      = factory.SubFactory(OrganizationFactory)
    periodo           = factory.LazyFunction(lambda: timezone.now().date().replace(day=1))
    vendedor_nombre   = factory.LazyFunction(lambda: fake.name())
    producto_nombre   = factory.LazyFunction(lambda: fake.bs().title()[:100])
    codigo_producto   = factory.Sequence(lambda n: f'PROD-{n+1:03d}')
    zona_nombre       = factory.LazyFunction(lambda: fake.city())
    plan_cantidad     = Decimal('100.00')
    plan_venta_usd    = Decimal('5000.00')
    real_cantidad     = Decimal('80.00')
    real_venta_usd    = Decimal('4000.00')


class CompetenciaRegistroFactory(DjangoModelFactory):
    class Meta:
        model = 'competencia.CompetenciaRegistro'

    organization   = factory.SubFactory(OrganizationFactory)
    fecha          = factory.LazyFunction(lambda: timezone.now().date())
    vendedor       = factory.SubFactory(UserFactory)
    producto       = factory.LazyFunction(lambda: fake.bs().title()[:100])
    competidor     = factory.LazyFunction(lambda: fake.last_name() + ' Distribuidora')
    precio_comp    = Decimal('100.00')
    precio_nuestro = Decimal('110.00')


# ── Fixtures de pytest ─────────────────────────────────────────────────────────

@pytest.fixture
def org():
    return OrganizationFactory()


@pytest.fixture
def org_inactiva():
    return OrganizationFactory(is_active=False)


@pytest.fixture
def gerente(org):
    return UserFactory(organization=org, role='gerente')


@pytest.fixture
def vendedor(org):
    return VendedorFactory(organization=org)


@pytest.fixture
def superadmin():
    return SuperadminFactory()


@pytest.fixture
def cliente(org):
    return ClienteFactory(organization=org)


@pytest.fixture
def pedido(org, gerente, cliente):
    return PedidoFactory(
        organization=org,
        vendedor=gerente,
        cliente=cliente,
    )


@pytest.fixture
def pedido_con_items(pedido):
    """Pedido con 2 ítems y total calculado."""
    PedidoItemFactory(pedido=pedido, cantidad=Decimal('5'), precio=Decimal('100'))
    PedidoItemFactory(pedido=pedido, cantidad=Decimal('3'), precio=Decimal('50'))
    pedido.recalcular_total()
    pedido.refresh_from_db()
    return pedido


@pytest.fixture
def client_gerente(client, gerente):
    """Cliente HTTP autenticado como gerente."""
    client.force_login(gerente)
    return client


@pytest.fixture
def client_vendedor(client, vendedor):
    """Cliente HTTP autenticado como vendedor."""
    client.force_login(vendedor)
    return client


@pytest.fixture
def client_superadmin(client, superadmin):
    """Cliente HTTP autenticado como superadmin."""
    client.force_login(superadmin)
    return client


@pytest.fixture
def vehiculo(org):
    return VehiculoFactory(organization=org)


@pytest.fixture
def viaje(org, vehiculo, gerente):
    return ViajeFactory(
        organization=org,
        vehiculo=vehiculo,
        chofer=gerente,
    )


# ── Factories para Productos e Inventario ──────────────────────────────────────

class CategoriaProductoFactory(DjangoModelFactory):
    class Meta:
        model = 'productos.CategoriaProducto'

    organization = factory.SubFactory(OrganizationFactory)
    nombre       = factory.Sequence(lambda n: f'Categoria {n+1}')


class ProductoFactory(DjangoModelFactory):
    class Meta:
        model = 'productos.Producto'

    organization   = factory.SubFactory(OrganizationFactory)
    nombre         = factory.Sequence(lambda n: f'Producto {n+1}')
    sku            = factory.Sequence(lambda n: f'SKU-{n+1:04d}')
    categoria      = factory.SubFactory(CategoriaProductoFactory)
    precio_base    = Decimal('100.00')
    unidad         = 'unidad'
    peso_kg        = Decimal('1.50')
    exento_iva     = True
    is_active      = True


class LoteFactory(DjangoModelFactory):
    class Meta:
        model = 'productos.Lote'

    producto            = factory.SubFactory(ProductoFactory)
    codigo_lote         = factory.Sequence(lambda n: f'LOTE-{n+1:04d}')
    fecha_elaboracion   = factory.LazyFunction(lambda: timezone.now().date())
    fecha_caducidad     = factory.LazyFunction(
        lambda: timezone.now().date() + timezone.timedelta(days=30)
    )
    cantidad_inicial    = Decimal('1000.00')
    cantidad_disponible = Decimal('1000.00')
    costo_unitario      = Decimal('50.00')
    is_active           = True


# ── Fixtures de Productos ──────────────────────────────────────────────────────

@pytest.fixture
def producto(org):
    cat = CategoriaProductoFactory(organization=org)
    return ProductoFactory(organization=org, categoria=cat)


@pytest.fixture
def lote(producto):
    return LoteFactory(producto=producto)
