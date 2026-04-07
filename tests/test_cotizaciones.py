"""
Tests del módulo de cotizaciones:
- CRUD de cotizaciones
- Numeración automática por organización
- Métodos de modelo (puede_editarse, puede_convertirse)
- Conversión a pedido
- Cambios de estado
"""
import pytest
from decimal import Decimal
from django.urls import reverse

from apps.cotizaciones.models import Cotizacion, CotizacionItem
from apps.cotizaciones.utils import generar_numero_cotizacion
from .conftest import (
    ClienteFactory,
    OrganizationFactory,
    PedidoFactory,
    UserFactory,
)


# ── Factories locales ──────────────────────────────────────────────────────────

import factory
from factory.django import DjangoModelFactory
from django.utils import timezone


class CotizacionFactory(DjangoModelFactory):
    class Meta:
        model = 'cotizaciones.Cotizacion'

    organization = factory.SubFactory(OrganizationFactory)
    numero = factory.Sequence(lambda n: f'COT-{n+1:04d}')
    fecha = factory.LazyFunction(lambda: timezone.now().date())
    cliente = factory.SubFactory(ClienteFactory)
    vendedor = factory.SubFactory(UserFactory)
    estado = 'Borrador'
    total = Decimal('0.00')


class CotizacionItemFactory(DjangoModelFactory):
    class Meta:
        model = 'cotizaciones.CotizacionItem'

    cotizacion = factory.SubFactory(CotizacionFactory)
    producto = factory.Sequence(lambda n: f'Producto {n+1}')
    cantidad = Decimal('5.00')
    precio = Decimal('100.00')
    exento_iva = True
    monto_iva = Decimal('0.00')


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def cotizacion(org, gerente, cliente):
    return CotizacionFactory(
        organization=org,
        vendedor=gerente,
        cliente=cliente,
    )


@pytest.fixture
def cotizacion_con_items(cotizacion):
    """Cotización con 2 ítems y total calculado."""
    CotizacionItemFactory(
        cotizacion=cotizacion,
        organization=cotizacion.organization,
        cantidad=Decimal('3'),
        precio=Decimal('100'),
    )
    CotizacionItemFactory(
        cotizacion=cotizacion,
        organization=cotizacion.organization,
        cantidad=Decimal('2'),
        precio=Decimal('50'),
    )
    cotizacion.recalcular_total()
    cotizacion.refresh_from_db()
    return cotizacion


@pytest.fixture
def cotizacion_aceptada(org, gerente, cliente):
    cot = CotizacionFactory(
        organization=org,
        vendedor=gerente,
        cliente=cliente,
        estado='Aceptada',
    )
    CotizacionItemFactory(
        cotizacion=cot,
        organization=org,
        cantidad=Decimal('2'),
        precio=Decimal('50'),
    )
    cot.recalcular_total()
    cot.refresh_from_db()
    return cot


@pytest.fixture
def cotizacion_convertida(org, gerente, cliente):
    """Cotización ya convertida a pedido."""
    pedido = PedidoFactory(organization=org, vendedor=gerente, cliente=cliente)
    cot = CotizacionFactory(
        organization=org,
        vendedor=gerente,
        cliente=cliente,
        estado='Convertida',
        pedido_generado=pedido,
    )
    return cot


# ── Tests de numeración ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNumeracionCotizaciones:
    """Tests de la numeración correlativa COT-XXXX por organización."""

    def test_primer_numero_es_cot_000001(self, org):
        """La primera cotización de una org recibe COT-000001."""
        numero = generar_numero_cotizacion(org)
        assert numero == 'COT-000001'

    def test_segundo_numero_es_cot_000002(self, org):
        """Los números son correlativos."""
        generar_numero_cotizacion(org)
        numero = generar_numero_cotizacion(org)
        assert numero == 'COT-000002'

    def test_numeracion_independiente_por_org(self, org):
        """Dos organizaciones distintas tienen numeración independiente."""
        otra_org = OrganizationFactory()
        # Consumir 3 números en otra org
        generar_numero_cotizacion(otra_org)
        generar_numero_cotizacion(otra_org)
        generar_numero_cotizacion(otra_org)

        # La org original debe empezar en 1
        numero = generar_numero_cotizacion(org)
        assert numero == 'COT-000001'


# ── Tests de CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCotizacionCRUD:
    """Tests de creación, lectura y totales de cotizaciones."""

    def test_crear_cotizacion_asigna_numero(self, org, gerente, cliente):
        """Al crear una cotización se asigna número automático."""
        numero = generar_numero_cotizacion(org)
        cot = CotizacionFactory(
            organization=org,
            vendedor=gerente,
            cliente=cliente,
            numero=numero,
        )
        assert cot.numero.startswith('COT-')

    def test_total_se_calcula_correctamente(self, cotizacion):
        """recalcular_total suma los items correctamente."""
        CotizacionItemFactory(
            cotizacion=cotizacion,
            organization=cotizacion.organization,
            cantidad=Decimal('5'),
            precio=Decimal('100'),
        )
        cotizacion.recalcular_total()
        cotizacion.refresh_from_db()
        assert cotizacion.subtotal == Decimal('500.00')
        assert cotizacion.total == Decimal('500.00')

    def test_total_acumula_multiples_items(self, cotizacion):
        """Varios ítems se suman correctamente."""
        CotizacionItemFactory(
            cotizacion=cotizacion,
            organization=cotizacion.organization,
            cantidad=Decimal('3'),
            precio=Decimal('100'),
        )
        CotizacionItemFactory(
            cotizacion=cotizacion,
            organization=cotizacion.organization,
            cantidad=Decimal('2'),
            precio=Decimal('50'),
        )
        cotizacion.recalcular_total()
        cotizacion.refresh_from_db()
        # 3*100 + 2*50 = 300 + 100 = 400
        assert cotizacion.subtotal == Decimal('400.00')

    def test_subtotal_item_es_property(self, cotizacion):
        """El subtotal del ítem es calculado como property."""
        item = CotizacionItemFactory(
            cotizacion=cotizacion,
            organization=cotizacion.organization,
            cantidad=Decimal('4'),
            precio=Decimal('25'),
        )
        assert item.subtotal == Decimal('100.00')

    def test_str_cotizacion(self, cotizacion):
        """__str__ muestra número y cliente."""
        resultado = str(cotizacion)
        assert cotizacion.numero in resultado
        assert str(cotizacion.cliente) in resultado


# ── Tests de métodos de negocio ────────────────────────────────────────────────

@pytest.mark.django_db
class TestCotizacionMetodosNegocio:
    """Tests de puede_editarse y puede_convertirse."""

    def test_borrador_puede_editarse(self, cotizacion):
        """Cotización en Borrador puede editarse."""
        assert cotizacion.puede_editarse() is True

    def test_enviada_puede_editarse(self, cotizacion):
        """Cotización Enviada puede editarse."""
        cotizacion.estado = 'Enviada'
        cotizacion.save(update_fields=['estado'])
        assert cotizacion.puede_editarse() is True

    def test_aceptada_puede_editarse(self, cotizacion):
        """Cotización Aceptada puede editarse (no está en ESTADOS_TERMINALES)."""
        cotizacion.estado = 'Aceptada'
        cotizacion.save(update_fields=['estado'])
        assert cotizacion.puede_editarse() is True

    def test_rechazada_no_puede_editarse(self, cotizacion):
        """Cotización Rechazada es terminal — no puede editarse."""
        cotizacion.estado = 'Rechazada'
        cotizacion.save(update_fields=['estado'])
        assert cotizacion.puede_editarse() is False

    def test_vencida_no_puede_editarse(self, cotizacion):
        """Cotización Vencida es terminal — no puede editarse."""
        cotizacion.estado = 'Vencida'
        cotizacion.save(update_fields=['estado'])
        assert cotizacion.puede_editarse() is False

    def test_convertida_no_puede_editarse(self, cotizacion_convertida):
        """Cotización Convertida es terminal — no puede editarse."""
        assert cotizacion_convertida.puede_editarse() is False

    def test_aceptada_puede_convertirse(self, cotizacion_aceptada):
        """Cotización Aceptada sin pedido puede convertirse."""
        assert cotizacion_aceptada.puede_convertirse() is True

    def test_borrador_no_puede_convertirse(self, cotizacion):
        """Cotización en Borrador no puede convertirse."""
        assert cotizacion.puede_convertirse() is False

    def test_no_convertir_si_ya_tiene_pedido(self, cotizacion_convertida):
        """Cotización Convertida (con pedido generado) no puede volver a convertirse."""
        assert cotizacion_convertida.puede_convertirse() is False


# ── Tests de conversión a pedido ───────────────────────────────────────────────

@pytest.mark.django_db
class TestConvertirAPedido:
    """Tests de la vista convertir_a_pedido."""

    def test_convertir_a_pedido_crea_pedido(self, client, org, gerente, cotizacion_aceptada):
        """POST a /convertir/ crea un Pedido y actualiza la cotización a Convertida."""
        from apps.pedidos.models import Pedido

        client.force_login(gerente)
        url = reverse('cotizaciones:convertir', args=[cotizacion_aceptada.pk])
        resp = client.post(url)

        # La respuesta redirige al detalle del pedido
        assert resp.status_code == 302

        # La cotización ahora es Convertida
        cotizacion_aceptada.refresh_from_db()
        assert cotizacion_aceptada.estado == 'Convertida'
        assert cotizacion_aceptada.pedido_generado is not None

        # Existe el pedido creado
        pedido = cotizacion_aceptada.pedido_generado
        assert pedido.cliente == cotizacion_aceptada.cliente
        assert pedido.vendedor == cotizacion_aceptada.vendedor

    def test_no_convertir_si_no_aceptada(self, client, org, gerente, cotizacion):
        """No se puede convertir una cotización que no está Aceptada."""
        client.force_login(gerente)
        url = reverse('cotizaciones:convertir', args=[cotizacion.pk])
        resp = client.post(url)

        # Redirige al detalle con error
        assert resp.status_code == 302
        cotizacion.refresh_from_db()
        assert cotizacion.estado == 'Borrador'
        assert cotizacion.pedido_generado is None

    def test_no_convertir_si_ya_convertida(self, client, org, gerente, cotizacion_convertida):
        """No se puede convertir una cotización ya Convertida."""
        client.force_login(gerente)
        url = reverse('cotizaciones:convertir', args=[cotizacion_convertida.pk])
        pedido_original_id = cotizacion_convertida.pedido_generado_id

        resp = client.post(url)
        assert resp.status_code == 302

        # El pedido_generado no cambió
        cotizacion_convertida.refresh_from_db()
        assert cotizacion_convertida.pedido_generado_id == pedido_original_id


# ── Tests de cambio de estado ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestCambiarEstado:
    """Tests de transiciones de estado en cotizaciones."""

    def test_borrador_puede_pasar_a_enviada(self, client, org, gerente, cotizacion):
        """Borrador → Enviada es una transición válida."""
        client.force_login(gerente)
        url = reverse('cotizaciones:cambiar_estado', args=[cotizacion.pk])
        resp = client.post(url, {'estado': 'Enviada'})

        assert resp.status_code == 302
        cotizacion.refresh_from_db()
        assert cotizacion.estado == 'Enviada'

    def test_enviada_puede_pasar_a_aceptada(self, client, org, gerente, cotizacion):
        """Enviada → Aceptada es una transición válida."""
        cotizacion.estado = 'Enviada'
        cotizacion.save(update_fields=['estado'])
        client.force_login(gerente)
        url = reverse('cotizaciones:cambiar_estado', args=[cotizacion.pk])
        resp = client.post(url, {'estado': 'Aceptada'})

        assert resp.status_code == 302
        cotizacion.refresh_from_db()
        assert cotizacion.estado == 'Aceptada'

    def test_enviada_puede_pasar_a_rechazada(self, client, org, gerente, cotizacion):
        """Enviada → Rechazada es una transición válida."""
        cotizacion.estado = 'Enviada'
        cotizacion.save(update_fields=['estado'])
        client.force_login(gerente)
        url = reverse('cotizaciones:cambiar_estado', args=[cotizacion.pk])
        resp = client.post(url, {'estado': 'Rechazada'})

        assert resp.status_code == 302
        cotizacion.refresh_from_db()
        assert cotizacion.estado == 'Rechazada'

    def test_rechazada_no_puede_cambiar_estado(self, client, org, gerente, cotizacion):
        """Una cotización Rechazada (terminal) no puede cambiar de estado."""
        cotizacion.estado = 'Rechazada'
        cotizacion.save(update_fields=['estado'])
        client.force_login(gerente)
        url = reverse('cotizaciones:cambiar_estado', args=[cotizacion.pk])
        resp = client.post(url, {'estado': 'Borrador'})

        assert resp.status_code == 302
        cotizacion.refresh_from_db()
        assert cotizacion.estado == 'Rechazada'


# ── Tests de eliminación ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEliminarCotizacion:
    """Tests de la vista eliminar."""

    def test_eliminar_borrador(self, client, org, gerente, cotizacion):
        """Cotización en Borrador puede eliminarse."""
        pk = cotizacion.pk
        client.force_login(gerente)
        url = reverse('cotizaciones:eliminar', args=[pk])
        resp = client.post(url)

        assert resp.status_code == 302
        assert not Cotizacion.objects.filter(pk=pk).exists()

    def test_no_eliminar_enviada(self, client, org, gerente, cotizacion):
        """Cotización Enviada no puede eliminarse."""
        cotizacion.estado = 'Enviada'
        cotizacion.save(update_fields=['estado'])
        pk = cotizacion.pk
        client.force_login(gerente)
        url = reverse('cotizaciones:eliminar', args=[pk])
        resp = client.post(url)

        assert resp.status_code == 302
        assert Cotizacion.objects.filter(pk=pk).exists()


# ── Tests de acceso y permisos ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestAccesoCotizaciones:
    """Tests de acceso por rol."""

    def test_lista_requiere_login(self, client):
        """La lista de cotizaciones requiere estar autenticado."""
        url = reverse('cotizaciones:lista')
        resp = client.get(url)
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_gerente_puede_ver_lista(self, client, org, gerente):
        """Un gerente puede acceder a la lista de cotizaciones."""
        client.force_login(gerente)
        url = reverse('cotizaciones:lista')
        resp = client.get(url)
        assert resp.status_code == 200

    def test_vendedor_puede_ver_lista(self, client, org, vendedor):
        """Un vendedor puede acceder a la lista de cotizaciones."""
        client.force_login(vendedor)
        url = reverse('cotizaciones:lista')
        resp = client.get(url)
        assert resp.status_code == 200

    def test_aislamiento_de_tenant(self, client, org, gerente, cotizacion):
        """Un usuario de otra organización no puede ver la cotización."""
        otra_org = OrganizationFactory()
        otro_gerente = UserFactory(organization=otra_org, role='gerente')
        client.force_login(otro_gerente)
        url = reverse('cotizaciones:detalle', args=[cotizacion.pk])
        resp = client.get(url)
        assert resp.status_code == 404
