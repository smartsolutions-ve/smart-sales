"""Vistas CRUD de clientes."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
    return render(request, 'clientes/form.html', {})


@login_required
@role_required('gerente', 'superadmin')
def detalle(request, pk):
    cliente = _get_cliente_or_404(pk, request.org)
    pedidos = cliente.pedido_set.select_related('vendedor').order_by('-fecha_pedido')
    return render(request, 'clientes/detalle.html', {'cliente': cliente, 'pedidos': pedidos})


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def editar(request, pk):
    cliente = _get_cliente_or_404(pk, request.org)
    if request.method == 'POST':
        return _guardar_cliente(request, cliente=cliente)
    return render(request, 'clientes/form.html', {'cliente': cliente})


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


def _guardar_cliente(request, cliente):
    data = request.POST
    nombre = data.get('nombre', '').strip()
    contacto = data.get('contacto', '').strip()
    telefono = data.get('telefono', '').strip()
    email = data.get('email', '').strip()
    direccion = data.get('direccion', '').strip()

    if not nombre:
        messages.error(request, 'El nombre del cliente es requerido.')
        return render(request, 'clientes/form.html', {'cliente': cliente})

    if cliente is None:
        cliente = Cliente(organization=request.org)

    cliente.nombre = nombre
    cliente.contacto = contacto
    cliente.telefono = telefono
    cliente.email = email
    cliente.direccion = direccion
    cliente.save()

    messages.success(request, f'Cliente "{cliente.nombre}" guardado.')
    return redirect('clientes:detalle', pk=cliente.pk)
