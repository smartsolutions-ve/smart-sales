"""
Tests del módulo de Cuentas por Cobrar (CxC).

Cubre:
- Cálculo de saldo (deuda pedidos - pagos)
- Registro de pagos y reducción de deuda
- Cálculo de aging por antigüedad
- Dashboard solo muestra clientes con deuda
- Aislamiento de pagos por organización (multi-tenant)
"""
import pytest
from decimal import Decimal
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.cxc.models import Pago
from apps.cxc.views import ESTADOS_ACTIVOS, _calcular_tramo_aging, _clientes_con_deuda

from .conftest import (
    ClienteFactory,
    OrganizationFactory,
    PedidoFactory,
    UserFactory,
)


# ── Factory local para Pago ────────────────────────────────────────────────────

def make_pago(cliente, user, monto, organization=None):
    """Crea un Pago de prueba."""
    return Pago.objects.create(
        cliente=cliente,
        organization=organization or cliente.organization,
        registrado_por=user,
        monto=monto,
        fecha=timezone.now().date(),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_pedido_con_monto(org, cliente, user, monto, estado='Entregado', dias_atras=0):
    """Crea un pedido con un total específico y estado dado."""
    fecha = timezone.now().date() - timedelta(days=dias_atras)
    pedido = PedidoFactory(
        organization=org,
        cliente=cliente,
        vendedor=user,
        estado=estado,
        total=monto,
        fecha_pedido=fecha,
    )
    return pedido


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSaldoCliente:
    """El saldo de un cliente es la suma de pedidos activos menos pagos recibidos."""

    def test_saldo_cliente_suma_pedidos_menos_pagos(self, org, gerente):
        """El saldo refleja deuda_pedidos - pagos usando subqueries de la vista."""
        cliente = ClienteFactory(organization=org)
        make_pedido_con_monto(org, cliente, gerente, Decimal('500'), estado='Entregado')
        make_pedido_con_monto(org, cliente, gerente, Decimal('300'), estado='Confirmado')
        make_pago(cliente, gerente, Decimal('200'))

        qs = _clientes_con_deuda(org).filter(pk=cliente.pk)
        c = qs.first()
        assert c is not None, "El cliente con deuda debe aparecer en el queryset"
        assert c.deuda_pedidos == Decimal('800')
        assert c.total_pagado == Decimal('200')
        assert c.saldo == Decimal('600')

    def test_pedido_cancelado_no_suma_a_deuda(self, org, gerente):
        """Los pedidos cancelados no entran en la deuda activa."""
        cliente = ClienteFactory(organization=org)
        make_pedido_con_monto(org, cliente, gerente, Decimal('1000'), estado='Cancelado')

        # El cliente no debe aparecer porque su saldo es 0
        qs = _clientes_con_deuda(org).filter(pk=cliente.pk)
        assert not qs.exists(), "Un cliente con solo pedidos cancelados no debe tener saldo"

    def test_cliente_sin_pedidos_no_aparece(self, org, gerente):
        """Un cliente sin pedidos activos no debe aparecer en el queryset."""
        cliente = ClienteFactory(organization=org)
        qs = _clientes_con_deuda(org).filter(pk=cliente.pk)
        assert not qs.exists()


@pytest.mark.django_db
class TestRegistrarPago:
    """El registro de un pago reduce la deuda visible del cliente."""

    def test_registrar_pago_reduce_deuda(self, org, gerente):
        """Registrar un pago aumenta total_pagado y reduce saldo."""
        cliente = ClienteFactory(organization=org)
        make_pedido_con_monto(org, cliente, gerente, Decimal('1000'), estado='Entregado')

        def _saldo():
            qs = _clientes_con_deuda(org).filter(pk=cliente.pk)
            c = qs.first()
            return c.saldo if c else Decimal('0')

        assert _saldo() == Decimal('1000')

        make_pago(cliente, gerente, Decimal('400'))
        assert _saldo() == Decimal('600')

        make_pago(cliente, gerente, Decimal('600'))
        # El saldo es 0, el cliente ya no aparece en _clientes_con_deuda
        assert _saldo() == Decimal('0')

    def test_pago_se_guarda_con_campos_correctos(self, org, gerente):
        """Un pago persiste con los datos proporcionados."""
        cliente = ClienteFactory(organization=org)
        pago = Pago.objects.create(
            cliente=cliente,
            organization=org,
            registrado_por=gerente,
            monto=Decimal('250'),
            metodo='ZELLE',
            referencia='REF-001',
            fecha=timezone.now().date(),
        )
        pago.refresh_from_db()
        assert pago.monto == Decimal('250')
        assert pago.metodo == 'ZELLE'
        assert pago.referencia == 'REF-001'
        assert pago.cliente == cliente
        assert pago.organization == org


@pytest.mark.django_db
class TestAgingCalculation:
    """El aging agrupa pedidos correctamente por antigüedad."""

    def test_aging_agrupa_por_antiguedad(self, org, gerente):
        """Pedidos de distintas fechas caen en los tramos correctos."""
        cliente = ClienteFactory(organization=org)

        p1 = make_pedido_con_monto(org, cliente, gerente, Decimal('100'), dias_atras=5)
        p2 = make_pedido_con_monto(org, cliente, gerente, Decimal('200'), dias_atras=45)
        p3 = make_pedido_con_monto(org, cliente, gerente, Decimal('300'), dias_atras=75)
        p4 = make_pedido_con_monto(org, cliente, gerente, Decimal('400'), dias_atras=100)

        assert _calcular_tramo_aging(p1.fecha_pedido) == 't0_30'
        assert _calcular_tramo_aging(p2.fecha_pedido) == 't31_60'
        assert _calcular_tramo_aging(p3.fecha_pedido) == 't61_90'
        assert _calcular_tramo_aging(p4.fecha_pedido) == 't90_mas'

    def test_aging_exacto_en_limites(self):
        """Los límites de tramo son inclusivos (30d es t0_30, 31d es t31_60)."""
        hoy = timezone.now().date()
        assert _calcular_tramo_aging(hoy - timedelta(days=30)) == 't0_30'
        assert _calcular_tramo_aging(hoy - timedelta(days=31)) == 't31_60'
        assert _calcular_tramo_aging(hoy - timedelta(days=60)) == 't31_60'
        assert _calcular_tramo_aging(hoy - timedelta(days=61)) == 't61_90'
        assert _calcular_tramo_aging(hoy - timedelta(days=90)) == 't61_90'
        assert _calcular_tramo_aging(hoy - timedelta(days=91)) == 't90_mas'


@pytest.mark.django_db
class TestDashboardCxC:
    """El dashboard solo muestra clientes con saldo positivo."""

    def test_dashboard_solo_clientes_con_deuda(self, org, gerente, client):
        """Clientes sin deuda no aparecen en el dashboard."""
        client.force_login(gerente)

        cliente_con_deuda = ClienteFactory(organization=org)
        cliente_sin_deuda = ClienteFactory(organization=org)

        # Solo el primero tiene pedido activo
        make_pedido_con_monto(org, cliente_con_deuda, gerente, Decimal('500'), estado='Entregado')

        response = client.get(reverse('cxc:dashboard'))
        assert response.status_code == 200

        clientes_en_contexto = [item['obj'] for item in response.context['clientes']]
        assert cliente_con_deuda in clientes_en_contexto
        assert cliente_sin_deuda not in clientes_en_contexto

    def test_dashboard_requiere_login(self, client):
        """Usuarios no autenticados son redirigidos al login."""
        response = client.get(reverse('cxc:dashboard'))
        assert response.status_code == 302
        assert '/login/' in response['Location']

    def test_kpis_son_correctos(self, org, gerente, client):
        """Los KPIs del dashboard coinciden con la deuda real."""
        client.force_login(gerente)

        c1 = ClienteFactory(organization=org)
        c2 = ClienteFactory(organization=org)
        make_pedido_con_monto(org, c1, gerente, Decimal('1000'), estado='Entregado')
        make_pedido_con_monto(org, c2, gerente, Decimal('500'), estado='Confirmado')

        response = client.get(reverse('cxc:dashboard'))
        assert response.context['total_por_cobrar'] == Decimal('1500')
        assert response.context['total_clientes'] == 2


@pytest.mark.django_db
class TestPagoAisladoPorOrg:
    """Los pagos de una organización no son visibles desde otra."""

    def test_pago_aislado_por_org(self, org, gerente):
        """Un pago en org_A no afecta el saldo de org_B."""
        org_b = OrganizationFactory()
        gerente_b = UserFactory(organization=org_b, role='gerente')
        cliente_b = ClienteFactory(organization=org_b)

        # Deuda en org_B
        make_pedido_con_monto(org_b, cliente_b, gerente_b, Decimal('800'), estado='Entregado')

        # Pago en org_A con cliente de org_A — no debe afectar org_B
        cliente_a = ClienteFactory(organization=org)
        make_pedido_con_monto(org, cliente_a, gerente, Decimal('500'), estado='Entregado')
        make_pago(cliente_a, gerente, Decimal('500'))

        # El saldo de org_B sigue siendo 800
        qs_b = _clientes_con_deuda(org_b).filter(pk=cliente_b.pk)
        c = qs_b.first()
        assert c is not None
        assert c.saldo == Decimal('800')

    def test_dashboard_no_mezcla_orgs(self, org, gerente, client):
        """El dashboard de org_A no muestra clientes de org_B."""
        client.force_login(gerente)

        org_b = OrganizationFactory()
        gerente_b = UserFactory(organization=org_b, role='gerente')
        cliente_b = ClienteFactory(organization=org_b)
        make_pedido_con_monto(org_b, cliente_b, gerente_b, Decimal('999'), estado='Entregado')

        response = client.get(reverse('cxc:dashboard'))
        assert response.status_code == 200
        clientes_en_contexto = [item['obj'] for item in response.context['clientes']]
        assert cliente_b not in clientes_en_contexto


@pytest.mark.django_db
class TestRegistrarPagoView:
    """Tests de la vista HTMX de registrar pago."""

    def test_get_retorna_formulario(self, org, gerente, client):
        """GET devuelve el formulario de pago."""
        client.force_login(gerente)
        cliente = ClienteFactory(organization=org)
        response = client.get(reverse('cxc:registrar_pago', kwargs={'pk': cliente.pk}))
        assert response.status_code == 200
        assert b'Registrar Pago' in response.content

    def test_post_crea_pago_y_retorna_lista(self, org, gerente, client):
        """POST válido crea el pago y devuelve el partial de pagos."""
        client.force_login(gerente)
        cliente = ClienteFactory(organization=org)

        data = {
            'fecha': timezone.now().date().isoformat(),
            'monto': '350.00',
            'metodo': 'TRANSFERENCIA',
            'referencia': 'TXN-001',
            'observaciones': '',
        }
        response = client.post(
            reverse('cxc:registrar_pago', kwargs={'pk': cliente.pk}),
            data=data,
        )
        assert response.status_code == 200
        assert Pago.objects.filter(cliente=cliente, monto=Decimal('350')).exists()
        assert response.get('HX-Trigger') == 'closeModal'

    def test_post_invalido_retorna_form_con_errores(self, org, gerente, client):
        """POST con monto vacío devuelve formulario con errores."""
        client.force_login(gerente)
        cliente = ClienteFactory(organization=org)

        data = {
            'fecha': timezone.now().date().isoformat(),
            'monto': '',  # campo requerido vacío
            'metodo': 'EFECTIVO',
        }
        response = client.post(
            reverse('cxc:registrar_pago', kwargs={'pk': cliente.pk}),
            data=data,
        )
        assert response.status_code == 200
        assert not Pago.objects.filter(cliente=cliente).exists()


@pytest.mark.django_db
class TestAgingReport:
    """Tests de la vista de aging report."""

    def test_aging_report_accesible(self, org, gerente, client):
        """El aging report carga correctamente."""
        client.force_login(gerente)
        response = client.get(reverse('cxc:aging'))
        assert response.status_code == 200

    def test_aging_csv_descarga(self, org, gerente, client):
        """La exportación CSV retorna el content-type correcto."""
        client.force_login(gerente)
        response = client.get(reverse('cxc:aging_csv'))
        assert response.status_code == 200
        assert 'text/csv' in response.get('Content-Type', '')
