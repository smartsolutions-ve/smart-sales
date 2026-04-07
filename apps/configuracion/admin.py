from django.contrib import admin
from .models import ConfiguracionEmpresa, UnidadMedida, ListaPrecio, MetodoPago, ZonaDespacho


@admin.register(ConfiguracionEmpresa)
class ConfiguracionEmpresaAdmin(admin.ModelAdmin):
    list_display = ['organization', 'moneda_principal', 'prefijo_pedido', 'metodo_valoracion_inventario']
    search_fields = ['organization__name', 'nombre_comercial', 'rif']
    readonly_fields = ['organization']


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'simbolo', 'tipo', 'es_base', 'activa', 'organization']
    list_filter = ['tipo', 'es_base', 'activa']
    search_fields = ['nombre', 'simbolo']


@admin.register(ListaPrecio)
class ListaPrecioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'descuento_porcentaje', 'es_default', 'activa', 'organization']
    list_filter = ['activa', 'es_default']


@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'dias_credito', 'activa', 'organization']
    list_filter = ['tipo', 'activa']


@admin.register(ZonaDespacho)
class ZonaDespachoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'costo_base_flete', 'dias_entrega_estimados', 'activa', 'organization']
    list_filter = ['activa']
