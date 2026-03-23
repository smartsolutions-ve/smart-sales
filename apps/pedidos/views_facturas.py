"""Vistas para gestión de facturas asociadas a pedidos."""
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from .models import Pedido, Factura


@login_required
@role_required('gerente')
@require_POST
def agregar_factura(request, pedido_pk):
    pedido = get_object_or_404(Pedido, pk=pedido_pk, organization=request.org)

    numero = request.POST.get('numero_factura', '').strip()
    fecha = request.POST.get('fecha_factura', '').strip()
    monto_str = request.POST.get('monto', '').strip()
    observaciones = request.POST.get('observaciones', '').strip()

    if not numero or not fecha or not monto_str:
        messages.error(request, 'Número, fecha y monto son requeridos.')
        return redirect('pedidos:detalle', pk=pedido.pk)

    try:
        monto = Decimal(monto_str)
        if monto <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        messages.error(request, 'El monto debe ser un número positivo.')
        return redirect('pedidos:detalle', pk=pedido.pk)

    Factura.objects.create(
        pedido=pedido,
        numero_factura=numero,
        fecha_factura=fecha,
        monto=monto,
        observaciones=observaciones,
        created_by=request.user,
    )
    messages.success(request, f'Factura {numero} agregada.')
    return redirect('pedidos:detalle', pk=pedido.pk)


@login_required
@role_required('gerente')
@require_POST
def eliminar_factura(request, pk):
    factura = get_object_or_404(Factura, pk=pk, pedido__organization=request.org)
    pedido_pk = factura.pedido_id
    numero = factura.numero_factura
    factura.delete()
    messages.success(request, f'Factura {numero} eliminada.')
    return redirect('pedidos:detalle', pk=pedido_pk)
