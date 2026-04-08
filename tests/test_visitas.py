"""
Tests del módulo de Visitas Comerciales.
Cubre: CRUD, control de acceso por rol, aislamiento tenant, filtros.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.visitas.models import VisitaComercial
from tests.conftest import (
    ClienteFactory,
    OrganizationFactory,
    UserFactory,
    VendedorFactory,
    VisitaFactory,
)

pytestmark = pytest.mark.django_db


# ── Helpers ────────────────────────────────────────────────────────────────────

def _login(client, user):
    client.force_login(user)
    return client


# ── Tests de modelo ────────────────────────────────────────────────────────────

class TestVisitaComercialModel:
    """Comportamiento del modelo VisitaComercial."""

    def test_str_representation(self, org):
        """__str__ muestra cliente y fecha."""
        cliente = ClienteFactory(organization=org)
        vendedor = UserFactory(organization=org)
        visita = VisitaFactory(
            organization=org,
            cliente=cliente,
            vendedor=vendedor,
        )
        assert str(cliente.nombre) in str(visita)
        assert str(visita.fecha) in str(visita)

    def test_marcar_realizada_cambia_estado(self, org):
        """marcar_realizada() actualiza estado a 'realizada'."""
        visita = VisitaFactory(organization=org, estado='pendiente')
        visita.marcar_realizada(resultado='Pedido tomado')
        visita.refresh_from_db()
        assert visita.estado == 'realizada'
        assert visita.resultado == 'Pedido tomado'

    def test_marcar_realizada_sin_resultado(self, org):
        """marcar_realizada() sin resultado no falla."""
        visita = VisitaFactory(organization=org, estado='pendiente')
        visita.marcar_realizada()
        visita.refresh_from_db()
        assert visita.estado == 'realizada'


# ── Tests de lista ─────────────────────────────────────────────────────────────

class TestListaVisitas:
    """Vista de lista de visitas."""

    def test_gerente_ve_todas_las_visitas_de_su_org(self, client, org):
        """Gerente ve visitas de todos los vendedores de su organización."""
        gerente = UserFactory(organization=org, role='gerente')
        vendedor1 = VendedorFactory(organization=org)
        vendedor2 = VendedorFactory(organization=org)
        VisitaFactory(organization=org, vendedor=vendedor1)
        VisitaFactory(organization=org, vendedor=vendedor2)

        _login(client, gerente)
        response = client.get(reverse('visitas:lista'))
        assert response.status_code == 200
        assert len(response.context['visitas']) == 2

    def test_vendedor_solo_ve_sus_visitas(self, client, org):
        """Vendedor solo ve sus propias visitas, no las de otros."""
        vendedor = VendedorFactory(organization=org)
        otro_vendedor = VendedorFactory(organization=org)
        VisitaFactory(organization=org, vendedor=vendedor)
        VisitaFactory(organization=org, vendedor=otro_vendedor)

        _login(client, vendedor)
        response = client.get(reverse('visitas:lista'))
        assert response.status_code == 200
        visitas = response.context['visitas']
        assert len(visitas) == 1
        assert visitas[0].vendedor == vendedor

    def test_aislamiento_tenant(self, client, org):
        """Gerente no ve visitas de otra organización."""
        otra_org = OrganizationFactory()
        gerente = UserFactory(organization=org, role='gerente')
        # Visita propia
        VisitaFactory(organization=org, vendedor=gerente)
        # Visita de otra org
        otro_vendedor = VendedorFactory(organization=otra_org)
        VisitaFactory(organization=otra_org, vendedor=otro_vendedor)

        _login(client, gerente)
        response = client.get(reverse('visitas:lista'))
        assert response.status_code == 200
        assert len(response.context['visitas']) == 1

    def test_filtro_por_estado(self, client, org):
        """Filtrar por estado 'realizada' devuelve solo esas visitas."""
        gerente = UserFactory(organization=org, role='gerente')
        VisitaFactory(organization=org, vendedor=gerente, estado='pendiente')
        VisitaFactory(organization=org, vendedor=gerente, estado='realizada')
        VisitaFactory(organization=org, vendedor=gerente, estado='cancelada')

        _login(client, gerente)
        response = client.get(reverse('visitas:lista'), {'estado': 'realizada'})
        assert response.status_code == 200
        visitas = response.context['visitas']
        assert len(visitas) == 1
        assert visitas[0].estado == 'realizada'

    def test_filtro_por_busqueda_cliente(self, client, org):
        """Buscar por nombre de cliente filtra correctamente."""
        gerente = UserFactory(organization=org, role='gerente')
        cliente_a = ClienteFactory(organization=org, nombre='Distribuidora Alpha')
        cliente_b = ClienteFactory(organization=org, nombre='Ferretería Beta')
        VisitaFactory(organization=org, vendedor=gerente, cliente=cliente_a)
        VisitaFactory(organization=org, vendedor=gerente, cliente=cliente_b)

        _login(client, gerente)
        response = client.get(reverse('visitas:lista'), {'q': 'Alpha'})
        assert response.status_code == 200
        visitas = response.context['visitas']
        assert len(visitas) == 1
        assert visitas[0].cliente.nombre == 'Distribuidora Alpha'


# ── Tests de creación ──────────────────────────────────────────────────────────

class TestCrearVisita:
    """Vista de creación de visitas."""

    def test_gerente_puede_crear_visita(self, client, org):
        """Gerente crea una visita asignando a un vendedor."""
        gerente = UserFactory(organization=org, role='gerente')
        cliente = ClienteFactory(organization=org)
        _login(client, gerente)

        response = client.post(reverse('visitas:crear'), {
            'cliente_id': cliente.pk,
            'vendedor_id': gerente.pk,
            'fecha': timezone.now().date().isoformat(),
            'tipo': 'presencial',
            'estado': 'pendiente',
            'objetivo': 'Presentar nuevos productos',
            'resultado': '',
        })
        assert response.status_code == 302
        assert VisitaComercial.objects.filter(organization=org).count() == 1

    def test_vendedor_crea_visita_auto_asignada(self, client, org):
        """Vendedor crea visita y el sistema lo asigna a sí mismo."""
        vendedor = VendedorFactory(organization=org)
        cliente = ClienteFactory(organization=org)
        _login(client, vendedor)

        response = client.post(reverse('visitas:crear'), {
            'cliente_id': cliente.pk,
            'fecha': timezone.now().date().isoformat(),
            'tipo': 'telefonica',
            'estado': 'pendiente',
            'objetivo': 'Llamada de seguimiento',
        })
        assert response.status_code == 302
        visita = VisitaComercial.objects.get(organization=org)
        assert visita.vendedor == vendedor

    def test_crear_sin_cliente_falla(self, client, org):
        """Crear sin cliente retorna formulario con error."""
        gerente = UserFactory(organization=org, role='gerente')
        _login(client, gerente)

        response = client.post(reverse('visitas:crear'), {
            'cliente_id': '',
            'fecha': timezone.now().date().isoformat(),
        })
        assert response.status_code == 200
        assert VisitaComercial.objects.filter(organization=org).count() == 0


# ── Tests de edición ───────────────────────────────────────────────────────────

class TestEditarVisita:
    """Vista de edición de visitas."""

    def test_gerente_puede_editar_cualquier_visita(self, client, org):
        """Gerente edita visita de cualquier vendedor."""
        gerente = UserFactory(organization=org, role='gerente')
        vendedor = VendedorFactory(organization=org)
        cliente = ClienteFactory(organization=org)
        visita = VisitaFactory(
            organization=org,
            vendedor=vendedor,
            cliente=cliente,
            objetivo='Objetivo original',
        )
        _login(client, gerente)

        response = client.post(reverse('visitas:editar', args=[visita.pk]), {
            'cliente_id': cliente.pk,
            'vendedor_id': vendedor.pk,
            'fecha': visita.fecha.isoformat(),
            'tipo': 'presencial',
            'estado': 'realizada',
            'objetivo': 'Objetivo actualizado',
            'resultado': 'Se cerró la venta',
        })
        assert response.status_code == 302
        visita.refresh_from_db()
        assert visita.objetivo == 'Objetivo actualizado'
        assert visita.estado == 'realizada'

    def test_vendedor_no_puede_editar_visita_ajena(self, client, org):
        """Vendedor recibe error al intentar editar visita de otro vendedor."""
        vendedor_a = VendedorFactory(organization=org)
        vendedor_b = VendedorFactory(organization=org)
        visita = VisitaFactory(organization=org, vendedor=vendedor_b)
        _login(client, vendedor_a)

        response = client.post(reverse('visitas:editar', args=[visita.pk]), {
            'cliente_id': visita.cliente.pk,
            'fecha': visita.fecha.isoformat(),
            'tipo': 'presencial',
            'estado': 'realizada',
        })
        assert response.status_code == 302
        # El estado no debe haber cambiado
        visita.refresh_from_db()
        assert visita.estado == 'pendiente'


# ── Tests de eliminación ───────────────────────────────────────────────────────

class TestEliminarVisita:
    """Vista de eliminación de visitas."""

    def test_gerente_puede_eliminar_visita(self, client, org):
        """Gerente elimina visita correctamente."""
        gerente = UserFactory(organization=org, role='gerente')
        visita = VisitaFactory(organization=org, vendedor=gerente)
        _login(client, gerente)

        response = client.post(reverse('visitas:eliminar', args=[visita.pk]))
        assert response.status_code == 302
        assert not VisitaComercial.objects.filter(pk=visita.pk).exists()

    def test_vendedor_elimina_su_propia_visita(self, client, org):
        """Vendedor puede eliminar sus propias visitas."""
        vendedor = VendedorFactory(organization=org)
        visita = VisitaFactory(organization=org, vendedor=vendedor)
        _login(client, vendedor)

        response = client.post(reverse('visitas:eliminar', args=[visita.pk]))
        assert response.status_code == 302
        assert not VisitaComercial.objects.filter(pk=visita.pk).exists()


# ── Tests de marcar realizada ──────────────────────────────────────────────────

class TestMarcarRealizada:
    """Vista de marcar visita como realizada."""

    def test_marcar_realizada_via_post(self, client, org):
        """POST a marcar_realizada cambia estado a 'realizada'."""
        gerente = UserFactory(organization=org, role='gerente')
        visita = VisitaFactory(organization=org, vendedor=gerente, estado='pendiente')
        _login(client, gerente)

        response = client.post(
            reverse('visitas:marcar_realizada', args=[visita.pk]),
            {'resultado': 'Visita exitosa, cliente interesado.'},
        )
        assert response.status_code == 302
        visita.refresh_from_db()
        assert visita.estado == 'realizada'
        assert visita.resultado == 'Visita exitosa, cliente interesado.'

    def test_marcar_realizada_sin_resultado_acepta(self, client, org):
        """Marcar realizada sin resultado no bloquea la operación."""
        gerente = UserFactory(organization=org, role='gerente')
        visita = VisitaFactory(organization=org, vendedor=gerente, estado='pendiente')
        _login(client, gerente)

        response = client.post(
            reverse('visitas:marcar_realizada', args=[visita.pk]),
            {},
        )
        assert response.status_code == 302
        visita.refresh_from_db()
        assert visita.estado == 'realizada'
