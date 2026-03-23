"""Tests del módulo Chat IA."""
import pytest
from django.urls import reverse
from apps.chat_ia.models import ChatMensaje
from .conftest import (
    OrganizationFactory, PedidoFactory, ClienteFactory,
    VehiculoFactory, VentaMensualFactory, FacturaFactory,
)


@pytest.mark.django_db
class TestChatMensaje:

    def test_mensaje_guardado_con_org_correcta(self, org, gerente):
        msg = ChatMensaje.objects.create(
            organization=org,
            user=gerente,
            rol='user',
            contenido='¿Cuántos pedidos hay?',
        )
        assert msg.organization == org
        assert msg.rol == 'user'

    def test_historial_filtrado_por_org(self, org, gerente):
        otra_org = OrganizationFactory()
        ChatMensaje.objects.create(
            organization=org, user=gerente,
            rol='user', contenido='Mensaje org A')
        ChatMensaje.objects.create(
            organization=otra_org, user=gerente,
            rol='user', contenido='Mensaje org B')
        mensajes_org = ChatMensaje.objects.filter(organization=org)
        assert mensajes_org.count() == 1
        assert mensajes_org.first().contenido == 'Mensaje org A'


@pytest.mark.django_db
class TestContextBuilder:

    def test_context_incluye_datos_de_la_org(self, org, gerente, cliente, pedido):
        from apps.chat_ia.services.context import build_context_for_org
        context = build_context_for_org(org)
        assert 'RESUMEN EJECUTIVO' in context
        assert 'ÚLTIMOS' in context

    def test_context_no_incluye_datos_de_otra_org(self, org, gerente):
        from apps.chat_ia.services.context import build_context_for_org
        otra_org = OrganizationFactory()
        cliente_otro = ClienteFactory(organization=otra_org)
        PedidoFactory(organization=otra_org, cliente=cliente_otro,
                      vendedor=gerente, numero='PED-9999')
        context = build_context_for_org(org)
        assert 'PED-9999' not in context

    def test_context_maneja_org_sin_datos(self, org):
        from apps.chat_ia.services.context import build_context_for_org
        context = build_context_for_org(org)
        assert isinstance(context, str)
        assert len(context) > 0

    def test_context_maneja_org_none(self):
        from apps.chat_ia.services.context import build_context_for_org
        context = build_context_for_org(None)
        assert isinstance(context, str)
        assert 'organización' in context.lower()

    def test_context_incluye_facturacion(self, org, gerente, cliente, pedido):
        from apps.chat_ia.services.context import build_context_for_org
        from apps.pedidos.models import Factura
        Factura.objects.create(
            pedido=pedido, numero_factura='FAC-001',
            fecha_factura='2026-03-01', monto=500, created_by=gerente)
        context = build_context_for_org(org)
        assert 'Facturación' in context or 'factur' in context.lower()

    def test_context_incluye_flotas(self, org):
        from apps.chat_ia.services.context import build_context_for_org
        VehiculoFactory(organization=org)
        context = build_context_for_org(org)
        assert 'Flotas' in context or 'Vehículo' in context or 'vehículo' in context.lower()

    def test_context_incluye_cuotas(self, org):
        from apps.chat_ia.services.context import build_context_for_org
        VentaMensualFactory(organization=org)
        context = build_context_for_org(org)
        assert 'Cuotas' in context or 'CUOTAS' in context or 'cumplimiento' in context.lower()


@pytest.mark.django_db
class TestAskView:

    def test_vendedor_no_tiene_acceso(self, client_vendedor):
        resp = client_vendedor.post(reverse('chat_ia:ask'),
                                   {'pregunta': 'Hola'})
        assert resp.status_code in (302, 403)

    def test_pregunta_vacia_retorna_400(self, client_gerente):
        resp = client_gerente.post(reverse('chat_ia:ask'),
                                  {'pregunta': '   '})
        assert resp.status_code == 400

    def test_pregunta_muy_larga_retorna_400(self, client_gerente):
        resp = client_gerente.post(reverse('chat_ia:ask'),
                                  {'pregunta': 'x' * 501})
        assert resp.status_code == 400

    def test_pregunta_guarda_mensaje_usuario_en_bd(
            self, client_gerente, org, gerente, monkeypatch, settings):
        from apps.chat_ia.services import gemini
        monkeypatch.setattr(
            gemini.GeminiBackend, 'ask',
            lambda self, **kw: 'Respuesta de prueba'
        )
        settings.CHAT_IA_BACKEND = 'apps.chat_ia.services.gemini.GeminiBackend'
        resp = client_gerente.post(
            reverse('chat_ia:ask'),
            {'pregunta': '¿Cuántos pedidos hay?'},
            HTTP_HX_REQUEST='true',
        )
        assert resp.status_code == 200
        assert ChatMensaje.objects.filter(
            organization=org, user=gerente, rol='user'
        ).exists()

    def test_rate_limit_bloquea_exceso(self, client_gerente, org, gerente):
        for _ in range(30):
            ChatMensaje.objects.create(
                organization=org, user=gerente,
                rol='user', contenido='Pregunta',
            )
        resp = client_gerente.post(
            reverse('chat_ia:ask'),
            {'pregunta': 'Una más'},
            HTTP_HX_REQUEST='true',
        )
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'límite' in content.lower()


@pytest.mark.django_db
class TestChatView:

    def test_chat_page_loads(self, client_gerente):
        resp = client_gerente.get(reverse('chat_ia:chat'))
        assert resp.status_code == 200

    def test_chat_flotante_format(self, client_gerente):
        resp = client_gerente.get(reverse('chat_ia:chat') + '?formato=flotante')
        assert resp.status_code == 200
