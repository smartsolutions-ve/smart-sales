"""Vistas del módulo de inteligencia de competencia."""
import csv

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator
from django.db.models import Q

from apps.accounts.decorators import role_required
from apps.pedidos.models import Cliente
from .models import CompetenciaRegistro


def _filtrar_competencia(request):
    """Aplica filtros y retorna queryset + contexto."""
    q = request.GET.get('q', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    registros = (
        CompetenciaRegistro.objects
        .filter(organization=request.org)
        .select_related('vendedor', 'cliente')
        .order_by('-fecha', '-created_at')
    )
    if q:
        registros = registros.filter(
            Q(producto__icontains=q) |
            Q(competidor__icontains=q) |
            Q(vendedor__first_name__icontains=q) |
            Q(vendedor__last_name__icontains=q)
        )
    if desde:
        registros = registros.filter(fecha__gte=desde)
    if hasta:
        registros = registros.filter(fecha__lte=hasta)

    return registros, {'q': q, 'desde': desde, 'hasta': hasta}


@login_required
@role_required('gerente', 'superadmin')
def lista(request):
    registros, filtros = _filtrar_competencia(request)
    paginator = Paginator(registros, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {'registros': page_obj, 'page_obj': page_obj, **filtros}
    return render(request, 'competencia/lista.html', context)


@login_required
@role_required('gerente', 'superadmin')
def exportar_csv(request):
    """Exportar registros de competencia a CSV."""
    registros, _ = _filtrar_competencia(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="competencia.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Producto', 'Competidor', 'Precio Comp.', 'Nuestro Precio', 'Diferencia', 'Vendedor', 'Cliente', 'Acción Tomada'])

    for r in registros:
        writer.writerow([
            r.fecha,
            r.producto,
            r.competidor,
            r.precio_comp or '',
            r.precio_nuestro or '',
            r.diferencia_precio if r.diferencia_precio is not None else '',
            r.vendedor.get_full_name() or r.vendedor.username,
            str(r.cliente) if r.cliente else '',
            r.accion_tomada,
        ])

    return response


@login_required
def crear(request):
    """Cualquier usuario (gerente o vendedor) puede crear registros."""
    if request.method == 'POST':
        return _guardar_registro(request)

    from django.utils import timezone
    clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
    return render(request, 'competencia/form.html', {
        'clientes': clientes,
        'today': timezone.now().date(),
    })


@login_required
@role_required('gerente', 'superadmin')
def editar(request, pk):
    registro = get_object_or_404(CompetenciaRegistro, pk=pk, organization=request.org)
    if request.method == 'POST':
        return _guardar_registro(request, registro=registro)

    clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
    return render(request, 'competencia/form.html', {'registro': registro, 'clientes': clientes})


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def eliminar(request, pk):
    registro = get_object_or_404(CompetenciaRegistro, pk=pk, organization=request.org)
    registro.delete()
    messages.success(request, 'Registro de competencia eliminado.')
    return redirect('competencia:lista')


def _guardar_registro(request, registro=None):
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
        return render(request, 'competencia/form.html', {'registro': registro, 'clientes': clientes})

    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)

    if registro:
        registro.producto = producto
        registro.competidor = competidor
        registro.fecha = fecha
        registro.cliente = cliente
        registro.precio_comp = precio_comp
        registro.precio_nuestro = precio_nuestro
        registro.accion_tomada = accion_tomada
        registro.save()
        messages.success(request, 'Registro de competencia actualizado.')
    else:
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

    if request.user.is_vendedor:
        return redirect('campo:index')
    return redirect('competencia:lista')
