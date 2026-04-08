"""Tests del sistema de alertas de stock mínimo."""
import pytest
from decimal import Decimal
from django.urls import reverse

from .conftest import (
    OrganizationFactory,
    UserFactory,
    ProductoFactory,
    LoteFactory,
    CategoriaProductoFactory,
)


# ── Tests de modelo ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProductoStockMinimo:
    """Tests de las propiedades stock_disponible y en_alerta_stock."""

    def test_stock_disponible_suma_lotes_activos(self):
        """stock_disponible suma correctamente los lotes activos."""
        producto = ProductoFactory()
        LoteFactory(producto=producto, cantidad_disponible=Decimal('100.00'), is_active=True)
        LoteFactory(producto=producto, cantidad_disponible=Decimal('50.00'), is_active=True)
        # Lote inactivo no debe contar
        LoteFactory(producto=producto, cantidad_disponible=Decimal('999.00'), is_active=False)

        assert producto.stock_disponible == Decimal('150.00')

    def test_stock_disponible_sin_lotes_retorna_cero(self):
        """stock_disponible retorna 0 cuando no hay lotes."""
        producto = ProductoFactory()
        assert producto.stock_disponible == 0

    def test_producto_sin_stock_minimo_no_alerta(self):
        """Producto con stock_minimo=0 nunca genera alerta."""
        producto = ProductoFactory(stock_minimo=Decimal('0'))
        LoteFactory(producto=producto, cantidad_disponible=Decimal('5.00'), is_active=True)

        assert producto.en_alerta_stock is False

    def test_producto_bajo_minimo_genera_alerta(self):
        """Producto con stock bajo el mínimo debe marcar en_alerta_stock como True."""
        producto = ProductoFactory(stock_minimo=Decimal('50.00'))
        LoteFactory(producto=producto, cantidad_disponible=Decimal('20.00'), is_active=True)

        assert producto.en_alerta_stock is True

    def test_producto_sobre_minimo_no_alerta(self):
        """Producto con stock igual o superior al mínimo no genera alerta."""
        producto = ProductoFactory(stock_minimo=Decimal('50.00'))
        LoteFactory(producto=producto, cantidad_disponible=Decimal('50.00'), is_active=True)

        assert producto.en_alerta_stock is False

    def test_producto_con_stock_cero_y_minimo_alerta(self):
        """Producto sin stock y con mínimo configurado genera alerta."""
        producto = ProductoFactory(stock_minimo=Decimal('10.00'))
        # Sin lotes

        assert producto.en_alerta_stock is True


# ── Tests de vista alertas_stock ───────────────────────────────────────────────

@pytest.mark.django_db
class TestAlertasStockVista:
    """Tests de la vista de listado de alertas de stock."""

    def test_producto_bajo_minimo_aparece_en_alerta(self, client, org, gerente):
        """Producto bajo mínimo aparece en la lista de alertas."""
        client.force_login(gerente)
        producto = ProductoFactory(
            organization=org, stock_minimo=Decimal('100.00'), is_active=True
        )
        LoteFactory(producto=producto, cantidad_disponible=Decimal('30.00'), is_active=True)

        url = reverse('productos:alertas_stock')
        response = client.get(url)

        assert response.status_code == 200
        assert producto.nombre in response.content.decode()

    def test_producto_sobre_minimo_no_aparece(self, client, org, gerente):
        """Producto con stock suficiente no aparece en alertas."""
        client.force_login(gerente)
        producto = ProductoFactory(
            organization=org, stock_minimo=Decimal('10.00'), is_active=True
        )
        LoteFactory(producto=producto, cantidad_disponible=Decimal('100.00'), is_active=True)

        url = reverse('productos:alertas_stock')
        response = client.get(url)

        assert response.status_code == 200
        assert producto.nombre not in response.content.decode()

    def test_producto_sin_stock_minimo_no_aparece(self, client, org, gerente):
        """Producto con stock_minimo=0 no aparece en alertas aunque tenga poco stock."""
        client.force_login(gerente)
        producto = ProductoFactory(
            organization=org, stock_minimo=Decimal('0'), is_active=True
        )
        LoteFactory(producto=producto, cantidad_disponible=Decimal('1.00'), is_active=True)

        url = reverse('productos:alertas_stock')
        response = client.get(url)

        assert response.status_code == 200
        assert producto.nombre not in response.content.decode()

    def test_aislamiento_tenant_alertas(self, client, org, gerente):
        """Productos de otra organización no aparecen en las alertas."""
        client.force_login(gerente)
        # Producto de otra org
        otra_org = OrganizationFactory()
        producto_ajeno = ProductoFactory(
            organization=otra_org, stock_minimo=Decimal('50.00'), is_active=True
        )
        LoteFactory(producto=producto_ajeno, cantidad_disponible=Decimal('1.00'), is_active=True)

        url = reverse('productos:alertas_stock')
        response = client.get(url)

        assert response.status_code == 200
        assert producto_ajeno.nombre not in response.content.decode()

    def test_vendedor_no_puede_acceder_a_alertas(self, client, org, vendedor):
        """El rol vendedor no tiene acceso a la vista de alertas."""
        client.force_login(vendedor)
        url = reverse('productos:alertas_stock')
        response = client.get(url)

        # Debe redirigir (403 o redirect a login)
        assert response.status_code in (302, 403)

    def test_sin_alertas_muestra_mensaje_ok(self, client, org, gerente):
        """Cuando no hay productos bajo mínimo, se muestra mensaje de estado OK."""
        client.force_login(gerente)
        url = reverse('productos:alertas_stock')
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert 'niveles adecuados' in content


# ── Tests de vista configurar_stock_minimo ─────────────────────────────────────

@pytest.mark.django_db
class TestConfigurarStockMinimo:
    """Tests de la vista que actualiza el stock mínimo de un producto."""

    def test_configurar_stock_minimo_actualiza(self, client, org, gerente):
        """POST válido actualiza el campo stock_minimo del producto."""
        client.force_login(gerente)
        producto = ProductoFactory(organization=org, stock_minimo=Decimal('0'))

        url = reverse('productos:configurar_stock_minimo', args=[producto.pk])
        response = client.post(url, {'stock_minimo': '75.50'})

        # Debe redirigir a alertas
        assert response.status_code == 302
        producto.refresh_from_db()
        assert producto.stock_minimo == Decimal('75.50')

    def test_configurar_stock_minimo_valor_invalido_no_actualiza(self, client, org, gerente):
        """POST con valor no numérico no cambia el stock_minimo."""
        client.force_login(gerente)
        producto = ProductoFactory(organization=org, stock_minimo=Decimal('10.00'))

        url = reverse('productos:configurar_stock_minimo', args=[producto.pk])
        response = client.post(url, {'stock_minimo': 'abc'})

        assert response.status_code == 302
        producto.refresh_from_db()
        # El valor no debe haber cambiado
        assert producto.stock_minimo == Decimal('10.00')

    def test_configurar_stock_minimo_otro_tenant_403(self, client, org, gerente):
        """No se puede modificar el stock_minimo de un producto de otra org."""
        client.force_login(gerente)
        otra_org = OrganizationFactory()
        producto_ajeno = ProductoFactory(organization=otra_org)

        url = reverse('productos:configurar_stock_minimo', args=[producto_ajeno.pk])
        response = client.post(url, {'stock_minimo': '100'})

        # Debe retornar 404 (get_object_or_404 con filtro de org)
        assert response.status_code == 404
