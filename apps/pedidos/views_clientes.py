"""Vistas CRUD de clientes."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import role_required
from .models import Cliente


def _get_cliente_or_404(pk, org):
    return get_object_or_404(Cliente, pk=pk, organization=org)


@login_required
@role_required('gerente', 'superadmin')
def lista(request):
    q = request.GET.get('q', '')
    clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
    if q:
        from django.db.models import Q as Qfilter
        clientes = clientes.filter(
            Qfilter(nombre__icontains=q) |
            Qfilter(telefono__icontains=q) |
            Qfilter(email__icontains=q) |
            Qfilter(contacto__icontains=q)
        )

    context = {'clientes': clientes, 'q': q}
    return render(request, 'clientes/lista.html', context)


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def crear(request):
    if request.method == 'POST':
        return _guardar_cliente(request, cliente=None)
    return render(request, 'clientes/form.html', _form_ctx(request))


@login_required
@role_required('gerente', 'superadmin')
def detalle(request, pk):
    from django.db.models import Sum
    cliente = _get_cliente_or_404(pk, request.org)
    pedidos = cliente.pedido_set.select_related('vendedor').order_by('-fecha_pedido')
    deuda_activa = cliente.pedido_set.filter(
        estado__in=['Pendiente', 'Confirmado', 'En Proceso']
    ).aggregate(t=Sum('total'))['t'] or 0
    return render(request, 'clientes/detalle.html', {
        'cliente': cliente,
        'pedidos': pedidos,
        'deuda_activa': deuda_activa,
    })


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def editar(request, pk):
    cliente = _get_cliente_or_404(pk, request.org)
    if request.method == 'POST':
        return _guardar_cliente(request, cliente=cliente)
    return render(request, 'clientes/form.html', {**_form_ctx(request), 'cliente': cliente})


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def eliminar(request, pk):
    cliente = _get_cliente_or_404(pk, request.org)
    if not cliente.puede_eliminarse():
        messages.error(request, 'No se puede eliminar un cliente con pedidos asociados.')
        return redirect('clientes:detalle', pk=cliente.pk)
    cliente.delete()
    messages.success(request, f'Cliente "{cliente.nombre}" eliminado.')
    return redirect('clientes:lista')


@login_required
def info_json(request, pk):
    """
    Retorna JSON con lista_precio_id y deuda_actual del cliente.
    Usado por el form de pedidos para ajustar precios y mostrar alerta de crédito.
    """
    cliente = get_object_or_404(Cliente, pk=pk, organization=request.org)
    from django.db.models import Sum
    deuda = cliente.pedido_set.filter(
        estado__in=['Pendiente', 'Confirmado', 'En Proceso']
    ).aggregate(total=Sum('total'))['total'] or 0

    return JsonResponse({
        'lista_precio_id': str(cliente.lista_precio_id) if cliente.lista_precio_id else '',
        'lista_precio_nombre': str(cliente.lista_precio) if cliente.lista_precio_id else '',
        'limite_credito': str(cliente.limite_credito),
        'dias_credito': cliente.dias_credito,
        'deuda_actual': str(deuda),
    })


def _form_ctx(request):
    """Contexto base para formulario de cliente: listas de precio disponibles."""
    from apps.configuracion.models import ListaPrecio
    listas = ListaPrecio.objects.filter(organization=request.org, activa=True).order_by('codigo')
    return {'listas_precio': listas}


def _guardar_cliente(request, cliente):
    from decimal import Decimal
    from apps.configuracion.models import ListaPrecio

    data = request.POST
    nombre = data.get('nombre', '').strip()
    contacto = data.get('contacto', '').strip()
    telefono = data.get('telefono', '').strip()
    email = data.get('email', '').strip()
    direccion = data.get('direccion', '').strip()

    if not nombre:
        messages.error(request, 'El nombre del cliente es requerido.')
        return render(request, 'clientes/form.html', {**_form_ctx(request), 'cliente': cliente})

    if cliente is None:
        cliente = Cliente(organization=request.org)

    cliente.nombre = nombre
    cliente.contacto = contacto
    cliente.telefono = telefono
    cliente.email = email
    cliente.direccion = direccion

    # Crédito y lista de precios (opcionales)
    lista_precio_id = data.get('lista_precio_id', '').strip()
    if lista_precio_id:
        try:
            cliente.lista_precio = ListaPrecio.objects.get(pk=lista_precio_id, organization=request.org)
        except ListaPrecio.DoesNotExist:
            cliente.lista_precio = None
    else:
        cliente.lista_precio = None

    try:
        cliente.limite_credito = Decimal(data.get('limite_credito', '0') or '0')
    except Exception:
        cliente.limite_credito = Decimal('0')

    try:
        cliente.dias_credito = int(data.get('dias_credito', '0') or '0')
    except (ValueError, TypeError):
        cliente.dias_credito = 0

    cliente.save()

    messages.success(request, f'Cliente "{cliente.nombre}" guardado.')
    return redirect('clientes:detalle', pk=cliente.pk)
