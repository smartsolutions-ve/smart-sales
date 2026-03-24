"""Vistas del módulo de flotas."""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Sum, Count, Q

from apps.accounts.decorators import role_required
from apps.pedidos.models import Pedido
from .models import Vehiculo, Viaje, ViajeDetalle


# ── Vehículos ─────────────────────────────────────────────────────

@login_required
@role_required('gerente')
def vehiculos_lista(request):
    vehiculos = Vehiculo.objects.filter(organization=request.org).select_related('chofer_habitual')
    solo_activos = request.GET.get('activos', 'true') != 'false'
    if solo_activos:
        vehiculos = vehiculos.filter(is_active=True)

    return render(request, 'flotas/vehiculos_lista.html', {
        'vehiculos': vehiculos,
        'solo_activos': solo_activos,
    })


@login_required
@role_required('gerente')
@require_http_methods(['GET', 'POST'])
def vehiculo_crear(request):
    if request.method == 'POST':
        return _guardar_vehiculo(request, vehiculo=None)
    usuarios = _get_usuarios_org(request)
    return render(request, 'flotas/vehiculo_form.html', {'usuarios': usuarios})


@login_required
@role_required('gerente')
@require_http_methods(['GET', 'POST'])
def vehiculo_editar(request, pk):
    vehiculo = get_object_or_404(Vehiculo, pk=pk, organization=request.org)
    if request.method == 'POST':
        return _guardar_vehiculo(request, vehiculo=vehiculo)
    usuarios = _get_usuarios_org(request)
    return render(request, 'flotas/vehiculo_form.html', {'vehiculo': vehiculo, 'usuarios': usuarios})


def _guardar_vehiculo(request, vehiculo):
    data = request.POST
    placa = data.get('placa', '').strip().upper()
    marca = data.get('marca', '').strip()
    modelo_v = data.get('modelo', '').strip()
    capacidad = data.get('capacidad_kg', '').strip()
    chofer_id = data.get('chofer_habitual', '').strip() or None
    is_active = data.get('is_active') == 'on'

    if not placa or not capacidad:
        messages.error(request, 'Placa y capacidad son requeridos.')
        usuarios = _get_usuarios_org(request)
        return render(request, 'flotas/vehiculo_form.html', {'vehiculo': vehiculo, 'usuarios': usuarios})

    # Verificar placa única por org
    qs = Vehiculo.objects.filter(organization=request.org, placa=placa)
    if vehiculo:
        qs = qs.exclude(pk=vehiculo.pk)
    if qs.exists():
        messages.error(request, f'Ya existe un vehículo con placa "{placa}".')
        usuarios = _get_usuarios_org(request)
        return render(request, 'flotas/vehiculo_form.html', {'vehiculo': vehiculo, 'usuarios': usuarios})

    if vehiculo is None:
        vehiculo = Vehiculo(organization=request.org)

    vehiculo.placa = placa
    vehiculo.marca = marca
    vehiculo.modelo = modelo_v
    vehiculo.capacidad_kg = Decimal(capacidad)
    vehiculo.chofer_habitual_id = chofer_id
    vehiculo.is_active = is_active
    vehiculo.save()

    messages.success(request, f'Vehículo "{vehiculo.placa}" guardado.')
    return redirect('flotas:vehiculos')


# ── Viajes ────────────────────────────────────────────────────────

@login_required
@role_required('gerente')
def viajes_lista(request):
    viajes = (
        Viaje.objects
        .filter(organization=request.org)
        .select_related('vehiculo', 'chofer')
        .annotate(
            total_peso=Sum('detalles__peso_estimado_kg'),
            total_pedidos=Count('detalles'),
        )
    )

    # Filtros
    estado = request.GET.get('estado', '')
    fecha = request.GET.get('fecha', '')
    vehiculo_id = request.GET.get('vehiculo', '')

    if estado:
        viajes = viajes.filter(estado=estado)
    if fecha:
        viajes = viajes.filter(fecha=fecha)
    if vehiculo_id:
        viajes = viajes.filter(vehiculo_id=vehiculo_id)

    viajes = viajes.order_by('-fecha', '-created_at')

    vehiculos = Vehiculo.objects.filter(organization=request.org, is_active=True)

    return render(request, 'flotas/viajes_lista.html', {
        'viajes': viajes,
        'vehiculos': vehiculos,
        'estado_filtro': estado,
        'fecha_filtro': fecha,
        'vehiculo_filtro': vehiculo_id,
        'estados': Viaje.ESTADOS,
    })


@login_required
@role_required('gerente')
@require_http_methods(['GET', 'POST'])
def viaje_crear(request):
    if request.method == 'POST':
        return _guardar_viaje(request, viaje=None)

    vehiculos = Vehiculo.objects.filter(organization=request.org, is_active=True)
    usuarios = _get_usuarios_org(request)
    pedidos_disponibles = _get_pedidos_disponibles(request)

    return render(request, 'flotas/viaje_form.html', {
        'vehiculos': vehiculos,
        'usuarios': usuarios,
        'pedidos_disponibles': pedidos_disponibles,
    })


@login_required
@role_required('gerente')
def viaje_detalle(request, pk):
    viaje = get_object_or_404(
        Viaje.objects.select_related('vehiculo', 'chofer'),
        pk=pk, organization=request.org,
    )
    detalles = viaje.detalles.select_related('pedido', 'pedido__cliente').order_by('orden_entrega')
    return render(request, 'flotas/viaje_detalle.html', {
        'viaje': viaje,
        'detalles': detalles,
    })


@login_required
@role_required('gerente')
@require_http_methods(['GET', 'POST'])
def viaje_editar(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk, organization=request.org)
    if request.method == 'POST':
        return _guardar_viaje(request, viaje=viaje)

    vehiculos = Vehiculo.objects.filter(organization=request.org, is_active=True)
    usuarios = _get_usuarios_org(request)
    pedidos_disponibles = _get_pedidos_disponibles(request)
    # Incluir pedidos ya asignados a este viaje
    pedidos_asignados = viaje.detalles.values_list('pedido_id', flat=True)
    pedidos_ya = Pedido.objects.filter(pk__in=pedidos_asignados).select_related('cliente')
    detalles_dict = {d.pedido_id: d for d in viaje.detalles.all()}

    return render(request, 'flotas/viaje_form.html', {
        'viaje': viaje,
        'vehiculos': vehiculos,
        'usuarios': usuarios,
        'pedidos_disponibles': pedidos_disponibles | pedidos_ya,
        'detalles_dict': detalles_dict,
    })


@login_required
@role_required('gerente')
@require_POST
def viaje_cambiar_estado(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk, organization=request.org)
    nuevo_estado = request.POST.get('estado', '')

    estados_validos = [e[0] for e in Viaje.ESTADOS]
    if nuevo_estado not in estados_validos:
        messages.error(request, 'Estado inválido.')
        return redirect('flotas:detalle', pk=viaje.pk)

    viaje.estado = nuevo_estado
    viaje.save(update_fields=['estado', 'updated_at'])
    messages.success(request, f'Estado del viaje actualizado a "{nuevo_estado}".')
    return redirect('flotas:detalle', pk=viaje.pk)


@login_required
@role_required('gerente')
@require_POST
def viaje_eliminar(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk, organization=request.org)
    if not viaje.puede_eliminarse():
        messages.error(request, 'Solo se pueden eliminar viajes en estado "Programado".')
        return redirect('flotas:detalle', pk=viaje.pk)
    viaje.delete()
    messages.success(request, 'Viaje eliminado.')
    return redirect('flotas:lista')


# ── Dashboard Flotas ──────────────────────────────────────────────

@login_required
@role_required('gerente')
def dashboard_flotas(request):
    viajes = Viaje.objects.filter(organization=request.org)
    vehiculos = Vehiculo.objects.filter(organization=request.org, is_active=True)

    total_viajes = viajes.count()
    viajes_completados = viajes.filter(estado='Completado').count()
    total_vehiculos = vehiculos.count()

    # Utilización promedio de viajes completados
    viajes_con_peso = (
        viajes.filter(estado='Completado')
        .annotate(total_peso=Sum('detalles__peso_estimado_kg'))
    )
    utilizaciones = []
    for v in viajes_con_peso.select_related('vehiculo'):
        if v.vehiculo.capacidad_kg and v.total_peso:
            utilizaciones.append(float(v.total_peso) / float(v.vehiculo.capacidad_kg) * 100)
    utilizacion_promedio = round(sum(utilizaciones) / len(utilizaciones), 1) if utilizaciones else 0

    costo_total = viajes.filter(estado='Completado').aggregate(total=Sum('costo_flete'))['total'] or 0

    return render(request, 'flotas/dashboard.html', {
        'total_viajes': total_viajes,
        'viajes_completados': viajes_completados,
        'total_vehiculos': total_vehiculos,
        'utilizacion_promedio': utilizacion_promedio,
        'costo_total': costo_total,
    })


# ── Helpers ───────────────────────────────────────────────────────

def _get_usuarios_org(request):
    from apps.accounts.models import User
    if request.org:
        return User.objects.filter(organization=request.org, is_active=True)
    return User.objects.none()


def _get_pedidos_disponibles(request):
    return Pedido.objects.filter(
        organization=request.org,
        estado_despacho__in=['Pendiente Despacho', 'Programado'],
    ).exclude(
        estado='Cancelado',
    ).select_related('cliente')


def _guardar_viaje(request, viaje):
    data = request.POST
    vehiculo_id = data.get('vehiculo', '')
    chofer_id = data.get('chofer', '')
    fecha = data.get('fecha', '')
    km = data.get('km_recorridos', '').strip() or None
    costo = data.get('costo_flete', '').strip() or None
    observaciones = data.get('observaciones', '').strip()

    if not vehiculo_id or not chofer_id or not fecha:
        messages.error(request, 'Vehículo, chofer y fecha son requeridos.')
        return redirect(request.get_full_path())

    vehiculo = get_object_or_404(Vehiculo, pk=vehiculo_id, organization=request.org)

    # Obtener pedidos seleccionados y pesos
    pedido_ids = data.getlist('pedidos')
    if not pedido_ids:
        messages.error(request, 'Debe seleccionar al menos un pedido.')
        return redirect(request.get_full_path())

    if viaje is None:
        viaje = Viaje(organization=request.org, created_by=request.user)

    viaje.vehiculo = vehiculo
    viaje.chofer_id = chofer_id
    viaje.fecha = fecha
    viaje.km_recorridos = km
    viaje.costo_flete = costo
    viaje.observaciones = observaciones
    viaje.save()

    # Recrear detalles
    viaje.detalles.all().delete()
    for i, pid in enumerate(pedido_ids):
        peso = data.get(f'peso_{pid}', '0').strip()
        try:
            peso_decimal = Decimal(peso) if peso else Decimal('0')
        except InvalidOperation:
            peso_decimal = Decimal('0')

        ViajeDetalle.objects.create(
            viaje=viaje,
            pedido_id=pid,
            peso_estimado_kg=peso_decimal,
            orden_entrega=i + 1,
        )

    messages.success(request, f'Viaje del {viaje.fecha} guardado con {len(pedido_ids)} pedidos.')
    return redirect('flotas:detalle', pk=viaje.pk)
