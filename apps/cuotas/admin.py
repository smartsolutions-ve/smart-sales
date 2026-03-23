from django.contrib import admin
from .models import VentaMensual, TasaCambio, Zona


@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'organization']
    list_filter = ['organization']
    search_fields = ['nombre', 'codigo']


@admin.register(TasaCambio)
class TasaCambioAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'tasa_bs_por_usd', 'fuente', 'organization']
    list_filter = ['organization', 'fuente']


@admin.register(VentaMensual)
class VentaMensualAdmin(admin.ModelAdmin):
    list_display = ['periodo', 'vendedor_nombre', 'producto_nombre', 'zona_nombre', 'canal', 'organization']
    list_filter = ['organization', 'canal', 'periodo']
    search_fields = ['vendedor_nombre', 'producto_nombre', 'zona_nombre']
