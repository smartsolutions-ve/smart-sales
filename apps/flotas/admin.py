from django.contrib import admin
from .models import Vehiculo, Viaje, ViajeDetalle


class ViajeDetalleInline(admin.TabularInline):
    model = ViajeDetalle
    extra = 0
    raw_id_fields = ['pedido']


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ['placa', 'marca', 'modelo', 'capacidad_kg', 'is_active', 'organization']
    list_filter = ['is_active', 'organization']
    search_fields = ['placa', 'marca', 'modelo']


@admin.register(Viaje)
class ViajeAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'vehiculo', 'chofer', 'estado', 'organization']
    list_filter = ['estado', 'organization']
    inlines = [ViajeDetalleInline]
    raw_id_fields = ['vehiculo', 'chofer']


@admin.register(ViajeDetalle)
class ViajeDetalleAdmin(admin.ModelAdmin):
    list_display = ['viaje', 'pedido', 'peso_estimado_kg', 'orden_entrega']
    raw_id_fields = ['viaje', 'pedido']
