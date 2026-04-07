"""
Tests del módulo de configuración por empresa.
Cubre: creación automática por signal, modelos, numeración atómica.
"""
import pytest
from decimal import Decimal

from apps.configuracion.models import (
    ConfiguracionEmpresa,
    UnidadMedida,
    ListaPrecio,
    MetodoPago,
    ZonaDespacho,
)
from tests.conftest import OrganizationFactory


pytestmark = pytest.mark.django_db


# ── Signal: auto-creación al crear org ────────────────────────────────────────

class TestSignalConfiguracionInicial:
    def test_signal_crea_configuracion_al_crear_org(self):
        org = OrganizationFactory()
        assert ConfiguracionEmpresa.objects.filter(organization=org).exists()

    def test_configuracion_toma_nombre_de_org(self):
        org = OrganizationFactory(name='Distribuidora Pérez')
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.nombre_comercial == 'Distribuidora Pérez'

    def test_signal_crea_unidades_basicas(self):
        org = OrganizationFactory()
        simbolos = list(
            UnidadMedida.objects.filter(organization=org).values_list('simbolo', flat=True)
        )
        for esperado in ['und', 'cja', 'kg', 'g', 'L', 'm']:
            assert esperado in simbolos, f'Falta unidad con símbolo: {esperado}'

    def test_signal_crea_lista_precio_default(self):
        org = OrganizationFactory()
        lista_default = ListaPrecio.objects.filter(organization=org, es_default=True)
        assert lista_default.count() == 1
        assert lista_default.first().codigo == 'A'

    def test_signal_crea_metodos_pago_basicos(self):
        org = OrganizationFactory()
        tipos = list(
            MetodoPago.objects.filter(organization=org).values_list('tipo', flat=True)
        )
        assert 'CONTADO' in tipos
        assert 'TRANSFERENCIA' in tipos
        assert 'CREDITO' in tipos

    def test_signal_no_ejecuta_en_update(self):
        org = OrganizationFactory()
        count_inicial = ConfiguracionEmpresa.objects.filter(organization=org).count()
        # Actualizar org no debe crear una segunda configuración
        org.name = 'Nombre actualizado'
        org.save()
        assert ConfiguracionEmpresa.objects.filter(organization=org).count() == count_inicial

    def test_dos_orgs_tienen_configuraciones_independientes(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        assert ConfiguracionEmpresa.objects.filter(organization=org1).exists()
        assert ConfiguracionEmpresa.objects.filter(organization=org2).exists()
        assert (
            ConfiguracionEmpresa.objects.get(organization=org1).pk
            != ConfiguracionEmpresa.objects.get(organization=org2).pk
        )


# ── ConfiguracionEmpresa: valores por defecto ─────────────────────────────────

class TestConfiguracionEmpresaDefaults:
    def test_moneda_default_es_usd(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.moneda_principal == 'USD'

    def test_zona_horaria_default_es_caracas(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.zona_horaria == 'America/Caracas'

    def test_iva_default_es_16(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.iva_por_defecto == Decimal('16.00')

    def test_metodo_valoracion_default_es_fefo(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.metodo_valoracion_inventario == 'FEFO'

    def test_prefijo_pedido_default(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.prefijo_pedido == 'PED'

    def test_siguiente_numero_pedido_empieza_en_1(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        assert config.siguiente_numero_pedido == 1


# ── Numeración de documentos ──────────────────────────────────────────────────

class TestNumeracionPedidos:
    def test_get_numero_pedido_genera_correlativo(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        numero = config.get_numero_pedido()
        assert numero == 'PED-000001'

    def test_get_numero_pedido_incrementa_contador(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        config.get_numero_pedido()
        config.refresh_from_db()
        assert config.siguiente_numero_pedido == 2

    def test_get_numero_pedido_segunda_llamada(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        config.get_numero_pedido()
        segundo = config.get_numero_pedido()
        assert segundo == 'PED-000002'

    def test_numeracion_respeta_prefijo_personalizado(self):
        org = OrganizationFactory()
        config = ConfiguracionEmpresa.objects.get(organization=org)
        config.prefijo_pedido = 'VNT'
        config.digitos_pedido = 4
        config.save()
        numero = config.get_numero_pedido()
        assert numero == 'VNT-0001'

    def test_numeracion_orgs_son_independientes(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        c1 = ConfiguracionEmpresa.objects.get(organization=org1)
        c2 = ConfiguracionEmpresa.objects.get(organization=org2)
        c1.get_numero_pedido()
        c1.get_numero_pedido()
        # org2 no debe verse afectada
        assert c2.siguiente_numero_pedido == 1


# ── UnidadMedida ──────────────────────────────────────────────────────────────

class TestUnidadMedida:
    def test_unique_together_simbolo_por_org(self):
        from django.db import IntegrityError
        org = OrganizationFactory()
        # La unidad 'und' ya fue creada por el signal
        with pytest.raises(IntegrityError):
            UnidadMedida.objects.create(
                organization=org,
                nombre='Unidad duplicada',
                simbolo='und',
                tipo='CANTIDAD',
            )

    def test_mismo_simbolo_en_distinta_org_es_valido(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        # Ambas ya tienen 'und' por el signal — no debe fallar
        assert UnidadMedida.objects.filter(organization=org1, simbolo='und').exists()
        assert UnidadMedida.objects.filter(organization=org2, simbolo='und').exists()

    def test_str_muestra_nombre_y_simbolo(self):
        org = OrganizationFactory()
        u = UnidadMedida.objects.get(organization=org, simbolo='kg')
        assert 'kg' in str(u)
        assert 'Kilogramo' in str(u)


# ── ListaPrecio ───────────────────────────────────────────────────────────────

class TestListaPrecio:
    def test_solo_una_lista_puede_ser_default(self):
        org = OrganizationFactory()
        # La lista A ya es default (del signal)
        lista_b = ListaPrecio.objects.create(
            organization=org,
            nombre='Mayorista',
            codigo='B',
            descuento_porcentaje=Decimal('10.00'),
            es_default=True,
        )
        # La lista A ya no debe ser default
        lista_a = ListaPrecio.objects.get(organization=org, codigo='A')
        assert not lista_a.es_default
        assert lista_b.es_default

    def test_unique_together_codigo_por_org(self):
        from django.db import IntegrityError
        org = OrganizationFactory()
        with pytest.raises(IntegrityError):
            ListaPrecio.objects.create(
                organization=org,
                nombre='Duplicada',
                codigo='A',
                descuento_porcentaje=Decimal('5.00'),
            )


# ── MetodoPago ────────────────────────────────────────────────────────────────

class TestMetodoPago:
    def test_crear_metodo_pago(self):
        org = OrganizationFactory()
        MetodoPago.objects.create(
            organization=org,
            nombre='Pago móvil',
            tipo='TRANSFERENCIA',
        )
        assert MetodoPago.objects.filter(organization=org, nombre='Pago móvil').exists()

    def test_str_retorna_nombre(self):
        org = OrganizationFactory()
        m = MetodoPago.objects.get(organization=org, tipo='CONTADO')
        assert str(m) == m.nombre


# ── ZonaDespacho ──────────────────────────────────────────────────────────────

class TestZonaDespacho:
    def test_crear_zona_despacho(self):
        org = OrganizationFactory()
        zona = ZonaDespacho.objects.create(
            organization=org,
            nombre='Zona Norte',
            costo_base_flete=Decimal('15.00'),
            dias_entrega_estimados=2,
        )
        assert zona.pk is not None
        assert str(zona) == 'Zona Norte'
