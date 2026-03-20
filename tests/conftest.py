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
