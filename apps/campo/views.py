"""Vistas del formulario móvil para vendedores (campo)."""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from apps.accounts.decorators import role_required
from apps.pedidos.models import Cliente, Pedido, PedidoItem
from apps.pedidos.utils import generar_numero_pedido
from apps.competencia.models import CompetenciaRegistro


@login_required
def index(request):
    """Página principal del formulario de campo para vendedores."""
    # Los vendedores solo acceden a /campo/; gerentes también pueden
    mis_pedidos = (
        Pedido.objects
        .filter(organization=request.org, vendedor=request.user)
        .select_related('cliente')
        .order_by('-created_at')[:10]
    )
    context = {'mis_pedidos': mis_pedidos}
    return render(request, 'campo/index.html', context)


@login_required
def pedido_nuevo(request):
    """Formulario optimizado para crear pedidos desde el campo."""
    if request.method == 'POST':
        return _crear_pedido_campo(request)

    clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
    context = {'clientes': clientes}
    return render(request, 'campo/pedido_form.html', context)


@login_required
def competencia_nueva(request):
    """Formulario de competencia desde el campo."""
    if request.method == 'POST':
        return _crear_competencia_campo(request)

    clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
    return render(request, 'campo/competencia_form.html', {'clientes': clientes})


def _crear_competencia_campo(request):
    """Lógica para guardar competencia desde el formulario de campo."""
    from django.utils import timezone
    from django.shortcuts import get_object_or_404
    data = request.POST

    producto = data.get('producto', '').strip()
    competidor = data.get('competidor', '').strip()

    if not producto or not competidor:
        messages.error(request, 'Producto y competidor son requeridos.')
        clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
        return render(request, 'campo/competencia_form.html', {'clientes': clientes})

    fecha = data.get('fecha') or timezone.now().date()
    cliente_id = data.get('cliente_id') or None
    precio_comp = data.get('precio_comp') or None
    precio_nuestro = data.get('precio_nuestro') or None
    accion_tomada = data.get('accion_tomada', '').strip()

    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)

    CompetenciaRegistro.objects.create(
        organization=request.org,
        fecha=fecha,
        vendedor=request.user,
        cliente=cliente,
        producto=producto,
        competidor=competidor,
        precio_comp=precio_comp,
        precio_nuestro=precio_nuestro,
        accion_tomada=accion_tomada,
    )

    messages.success(request, 'Registro de competencia guardado.')
    return redirect('campo:index')


def _crear_pedido_campo(request):
    from django.utils import timezone
    data = request.POST

    cliente_id = data.get('cliente_id')
    cliente_nuevo = data.get('cliente_nuevo_nombre', '').strip()
    fecha_pedido = data.get('fecha_pedido') or timezone.now().date()
    fecha_entrega = data.get('fecha_entrega') or None
    observaciones = data.get('observaciones', '').strip()

    cliente = None
    if cliente_id:
        from django.shortcuts import get_object_or_404
        cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)
    elif cliente_nuevo:
        cliente, _ = Cliente.objects.get_or_create(
            organization=request.org,
            nombre=cliente_nuevo,
        )
    else:
        messages.error(request, 'Selecciona o escribe un cliente.')
        clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
        return render(request, 'campo/pedido_form.html', {'clientes': clientes})

    productos = data.getlist('items[][producto]')
    cantidades = data.getlist('items[][cantidad]')
    precios = data.getlist('items[][precio]')

    items_data = []
    for i, producto in enumerate(productos):
        producto = producto.strip()
        if not producto:
            continue
        try:
            cantidad = float(cantidades[i])
            precio = float(precios[i])
            if cantidad <= 0 or precio < 0:
                raise ValueError
        except (ValueError, IndexError):
            messages.error(request, f'El ítem "{producto}" debe tener cantidad > 0 y precio >= 0.')
            clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
            return render(request, 'campo/pedido_form.html', {'clientes': clientes})
        items_data.append({'producto': producto, 'cantidad': cantidad, 'precio': precio})

    if not items_data:
        messages.error(request, 'Agrega al menos un ítem al pedido.')
        clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
        return render(request, 'campo/pedido_form.html', {'clientes': clientes})

    from apps.pedidos.services import PedidoService
    try:
        pedido = PedidoService.guardar_pedido(
            organization=request.org,
            user=request.user,
            cliente=cliente,
            vendedor=request.user,
            fecha_pedido=fecha_pedido,
            items_data=items_data,
            fecha_entrega=fecha_entrega,
            observaciones=observaciones,
        )
    except Exception as e:
        messages.error(request, str(e))
        return render(request, 'campo/pedido_form.html', {
            'clientes': Cliente.objects.filter(organization=request.org).order_by('nombre')
        })

    # Notificar a gerentes por email
    from apps.pedidos.notifications import notificar_pedido_nuevo_campo
    notificar_pedido_nuevo_campo(pedido)

    messages.success(request, f'Pedido {pedido.numero} registrado correctamente.')
    return redirect('campo:index')
