"""Vistas del módulo de inteligencia de competencia."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator

from apps.accounts.decorators import role_required
from apps.pedidos.models import Cliente
from .models import CompetenciaRegistro


@login_required
@role_required('gerente', 'superadmin')
def lista(request):
    registros = (
        CompetenciaRegistro.objects
        .filter(organization=request.org)
        .select_related('vendedor', 'cliente')
        .order_by('-fecha', '-created_at')
    )
    paginator = Paginator(registros, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {'registros': page_obj, 'page_obj': page_obj}
    return render(request, 'competencia/lista.html', context)


@login_required
def crear(request):
    """Cualquier usuario (gerente o vendedor) puede crear registros."""
    if request.method == 'POST':
        return _guardar_registro(request)

    clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
    return render(request, 'competencia/form.html', {'clientes': clientes})


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def eliminar(request, pk):
    registro = get_object_or_404(CompetenciaRegistro, pk=pk, organization=request.org)
    registro.delete()
    messages.success(request, 'Registro de competencia eliminado.')
    return redirect('competencia:lista')


def _guardar_registro(request):
    from django.utils import timezone
    data = request.POST

    producto = data.get('producto', '').strip()
    competidor = data.get('competidor', '').strip()
    fecha = data.get('fecha') or timezone.now().date()
    cliente_id = data.get('cliente_id') or None
    precio_comp = data.get('precio_comp') or None
    precio_nuestro = data.get('precio_nuestro') or None
    accion_tomada = data.get('accion_tomada', '').strip()

    if not producto or not competidor:
        messages.error(request, 'Producto y competidor son requeridos.')
        clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
        return render(request, 'competencia/form.html', {'clientes': clientes})

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
    # Redirigir según rol
    if request.user.is_vendedor:
        return redirect('campo:index')
    return redirect('competencia:lista')
