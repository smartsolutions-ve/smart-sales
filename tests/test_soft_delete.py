"""
Tests Fase 1 — SoftDeleteModel

Usa Cliente como modelo de prueba (hereda TenantModel + SoftDeleteModel).

Cubre:
- soft_delete(): is_deleted=True, deleted_at asignado, deleted_by con/sin usuario
- restore(): resetea todos los campos
- objects manager: NO retorna eliminados
- all_objects manager: SÍ retorna eliminados
- Persistencia en BD de ambas operaciones
- Independencia entre objetos
"""
import pytest
from django.utils import timezone

from apps.pedidos.models import Cliente

from tests.conftest import OrganizationFactory, UserFactory, ClienteFactory


@pytest.mark.django_db
class TestSoftDelete:

    def test_soft_delete_marca_is_deleted(self):
        org = OrganizationFactory()
        cliente = ClienteFactory(organization=org)

        assert cliente.is_deleted is False
        cliente.soft_delete()
        assert cliente.is_deleted is True

    def test_soft_delete_asigna_deleted_at(self):
        org = OrganizationFactory()
        cliente = ClienteFactory(organization=org)

        assert cliente.deleted_at is None
        cliente.soft_delete()
        assert cliente.deleted_at is not None

    def test_soft_delete_asigna_deleted_by_con_usuario(self):
        org = OrganizationFactory()
        usuario = UserFactory(organization=org)
        cliente = ClienteFactory(organization=org)

        cliente.soft_delete(user=usuario)
        assert cliente.deleted_by == usuario

    def test_soft_delete_sin_usuario_deleted_by_es_none(self):
        org = OrganizationFactory()
        cliente = ClienteFactory(organization=org)

        cliente.soft_delete()
        assert cliente.deleted_by is None

    def test_restore_limpia_todos_los_campos(self):
        org = OrganizationFactory()
        usuario = UserFactory(organization=org)
        cliente = ClienteFactory(organization=org)

        cliente.soft_delete(user=usuario)
        assert cliente.is_deleted is True

        cliente.restore()

        assert cliente.is_deleted is False
        assert cliente.deleted_at is None
        assert cliente.deleted_by is None

    def test_objects_excluye_eliminados(self):
        org = OrganizationFactory()
        activo = ClienteFactory(organization=org, nombre='Activo')
        eliminado = ClienteFactory(organization=org, nombre='Eliminado')

        eliminado.soft_delete()

        qs = Cliente.objects.filter(organization=org)
        assert qs.filter(pk=activo.pk).exists()
        assert not qs.filter(pk=eliminado.pk).exists()

    def test_all_objects_incluye_eliminados(self):
        org = OrganizationFactory()
        activo = ClienteFactory(organization=org, nombre='Activo')
        eliminado = ClienteFactory(organization=org, nombre='Eliminado')

        eliminado.soft_delete()

        qs = Cliente.all_objects.filter(organization=org)
        assert qs.filter(pk=activo.pk).exists()
        assert qs.filter(pk=eliminado.pk).exists()

    def test_soft_delete_persiste_en_bd(self):
        org = OrganizationFactory()
        cliente = ClienteFactory(organization=org)
        pk = cliente.pk

        cliente.soft_delete()

        from_db = Cliente.all_objects.get(pk=pk)
        assert from_db.is_deleted is True
        assert from_db.deleted_at is not None

    def test_restore_persiste_en_bd(self):
        org = OrganizationFactory()
        usuario = UserFactory(organization=org)
        cliente = ClienteFactory(organization=org)
        pk = cliente.pk

        cliente.soft_delete(user=usuario)
        cliente.restore()

        from_db = Cliente.all_objects.get(pk=pk)
        assert from_db.is_deleted is False
        assert from_db.deleted_at is None
        assert from_db.deleted_by is None

    def test_soft_delete_no_afecta_otros_objetos(self):
        org = OrganizationFactory()
        cliente_a = ClienteFactory(organization=org, nombre='A')
        cliente_b = ClienteFactory(organization=org, nombre='B')

        cliente_a.soft_delete()

        # B sigue siendo accesible por el manager estándar
        assert Cliente.objects.filter(pk=cliente_b.pk).exists()
        # A no
        assert not Cliente.objects.filter(pk=cliente_a.pk).exists()

    def test_objects_count_correcto_con_mezcla(self):
        org = OrganizationFactory()
        for i in range(3):
            ClienteFactory(organization=org, nombre=f'Activo {i}')
        for i in range(2):
            c = ClienteFactory(organization=org, nombre=f'Eliminado {i}')
            c.soft_delete()

        assert Cliente.objects.filter(organization=org).count() == 3
        assert Cliente.all_objects.filter(organization=org).count() == 5
