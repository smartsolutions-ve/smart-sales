"""Vistas de reportes y analytics."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from decimal import Decimal

from apps.accounts.decorators import role_required
from apps.pedidos.models import Pedido, Cliente
from apps.accounts.models import User


@login_required
@role_required('gerente', 'superadmin')
def vendedores(request):
    """Reporte de métricas por vendedor (RN-018)."""
    vendedores_qs = (
        User.objects
        .filter(organization=request.org, role__in=['gerente', 'vendedor'], is_active=True)
        .annotate(
            total_vendido=Sum(
                'pedidos_vendedor__total',
                filter=Q(pedidos_vendedor__organization=request.org) &
                       ~Q(pedidos_vendedor__estado='Cancelado')
            ),
            cantidad_pedidos=Count(
                'pedidos_vendedor',
                filter=Q(pedidos_vendedor__organization=request.org) &
                       ~Q(pedidos_vendedor__estado='Cancelado')
            ),
            pedidos_entregados=Count(
                'pedidos_vendedor',
                filter=Q(pedidos_vendedor__organization=request.org,
                         pedidos_vendedor__estado='Entregado')
            ),
        )
        .order_by('-total_vendido')
    )

    context = {'vendedores': vendedores_qs}
    return render(request, 'reportes/vendedores.html', context)


@login_required
@role_required('gerente', 'superadmin')
def clientes(request):
    """Reporte de top clientes por monto acumulado (RN-019)."""
    clientes_qs = (
        Cliente.objects
        .filter(organization=request.org)
        .annotate(
            total_compras=Sum(
                'pedido__total',
                filter=~Q(pedido__estado='Cancelado')
            ),
            cantidad_pedidos=Count(
                'pedido',
                filter=~Q(pedido__estado='Cancelado')
            ),
        )
        .order_by('-total_compras')
    )

    context = {'clientes': clientes_qs}
    return render(request, 'reportes/clientes.html', context)
