"""
Tests del módulo accounts:
- Login y logout
- Redirección por rol
- Aislamiento de tenant (multi-tenancy)
- Middleware TenantMiddleware
"""
import pytest
from django.urls import reverse
from .conftest import (
    OrganizationFactory, UserFactory, VendedorFactory, SuperadminFactory
)


@pytest.mark.django_db
class TestLogin:
    """Tests del flujo de autenticación."""

    def test_login_correcto_gerente_redirige_a_dashboard(self, client, gerente):
        """Un gerente con credenciales correctas llega al dashboard."""
        url = reverse('accounts:login')
        resp = client.post(url, {
            'username': gerente.username,
            'password': 'testpass123',
        })
        assert resp.status_code == 302
        assert resp['Location'] == reverse('dashboard:index')

    def test_login_correcto_vendedor_redirige_a_campo(self, client, vendedor):
        """Un vendedor con credenciales correctas llega al formulario de campo."""
        url = reverse('accounts:login')
        resp = client.post(url, {
            'username': vendedor.username,
            'password': 'testpass123',
        })
        assert resp.status_code == 302
        assert resp['Location'] == reverse('campo:index')

    def test_login_correcto_superadmin_redirige_a_admin_panel(self, client, superadmin):
        """El superadmin llega al panel de administración."""
        url = reverse('accounts:login')
        resp = client.post(url, {
            'username': superadmin.username,
            'password': 'testpass123',
        })
        assert resp.status_code == 302
        assert resp['Location'] == reverse('admin_panel:index')

    def test_login_credenciales_incorrectas(self, client, gerente):
        """Credenciales incorrectas muestran error y no redirigen."""
        url = reverse('accounts:login')
        resp = client.post(url, {
            'username': gerente.username,
            'password': 'contraseña_incorrecta',
        })
        assert resp.status_code == 200
        assert 'incorrectos' in resp.content.decode()

    def test_login_org_inactiva_bloquea_acceso(self, client):
        """Un usuario de una organización inactiva no puede entrar."""
        org_inactiva = OrganizationFactory(is_active=False)
        usuario = UserFactory(organization=org_inactiva, role='gerente')

        url = reverse('accounts:login')
        resp = client.post(url, {
            'username': usuario.username,
            'password': 'testpass123',
        })
        # No debe redirigir — debe mostrar el formulario con mensaje
        assert resp.status_code == 200
        assert 'suspendida' in resp.content.decode().lower()

    def test_login_usuario_inactivo_bloqueado(self, client, org):
        """Un usuario con is_active=False no puede entrar."""
        usuario = UserFactory(organization=org, is_active=False)
        url = reverse('accounts:login')
        resp = client.post(url, {
            'username': usuario.username,
            'password': 'testpass123',
        })
        assert resp.status_code == 200

    def test_logout_redirige_a_login(self, client_gerente):
        """El logout redirige al login."""
        resp = client_gerente.get(reverse('accounts:logout'))
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_usuario_autenticado_en_login_redirige(self, client_gerente):
        """Un usuario ya autenticado que va al login es redirigido."""
        resp = client_gerente.get(reverse('accounts:login'))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestMultiTenancyAislamiento:
    """
    Tests críticos: verificar que un usuario de la organización A
    no puede ver ni modificar datos de la organización B.
    """

    def test_pedido_org_b_invisible_para_org_a(self, client_gerente, org):
        """Un pedido de otra organización devuelve 404."""
        from .conftest import PedidoFactory, OrganizationFactory
        otra_org = OrganizationFactory()
        pedido_ajeno = PedidoFactory(organization=otra_org)

        url = reverse('pedidos:detalle', kwargs={'pk': pedido_ajeno.pk})
        resp = client_gerente.get(url)
        assert resp.status_code == 404

    def test_cliente_org_b_invisible_para_org_a(self, client_gerente, org):
        """Un cliente de otra organización devuelve 404."""
        from .conftest import ClienteFactory, OrganizationFactory
        otra_org = OrganizationFactory()
        cliente_ajeno = ClienteFactory(organization=otra_org)

        url = reverse('clientes:detalle', kwargs={'pk': cliente_ajeno.pk})
        resp = client_gerente.get(url)
        assert resp.status_code == 404

    def test_lista_pedidos_solo_muestra_propios(self, client_gerente, org, pedido):
        """La lista de pedidos solo muestra los de la organización del usuario."""
        from .conftest import PedidoFactory, OrganizationFactory
        otra_org = OrganizationFactory()
        pedido_ajeno = PedidoFactory(organization=otra_org)

        url = reverse('pedidos:lista')
        resp = client_gerente.get(url)
        content = resp.content.decode()

        assert pedido.numero in content
        assert pedido_ajeno.numero not in content


@pytest.mark.django_db
class TestPermisosRoles:
    """Tests de control de acceso por rol."""

    def test_vendedor_no_accede_al_dashboard(self, client_vendedor):
        """Un vendedor redirigido al campo si intenta acceder al dashboard."""
        resp = client_vendedor.get(reverse('dashboard:index'))
        # Debe redirigir al campo
        assert resp.status_code in (302, 403)

    def test_vendedor_no_accede_a_pedidos(self, client_vendedor):
        """Un vendedor no puede ver la lista de pedidos gerencial."""
        resp = client_vendedor.get(reverse('pedidos:lista'))
        assert resp.status_code in (302, 403)

    def test_gerente_no_accede_al_panel_admin(self, client_gerente):
        """Un gerente no puede acceder al panel de superadmin."""
        resp = client_gerente.get(reverse('admin_panel:index'))
        assert resp.status_code in (302, 403)

    def test_usuario_no_autenticado_redirigido_a_login(self, client):
        """Un usuario no autenticado es redirigido al login."""
        resp = client.get(reverse('dashboard:index'))
        assert resp.status_code == 302
        assert '/login/' in resp['Location']
