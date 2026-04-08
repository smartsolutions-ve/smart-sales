"""
Vistas del módulo de Visitas Comerciales.
- Gerente/superadmin: ve todas las visitas de la organización con filtros.
- Vendedor: solo ve sus propias visitas.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.pedidos.models import Cliente

from .models import VisitaComercial


def _get_visitas_base(request):
    """
    Retorna queryset base de visitas filtrado por organización y rol.
    Gerente/superadmin ven todas; vendedor solo las suyas.
    """
    qs = (
        VisitaComercial.objects
        .filter(organization=request.org)
        .select_related('cliente', 'vendedor')
    )
    if request.user.is_vendedor:
        qs = qs.filter(vendedor=request.user)
    return qs


def _aplicar_filtros(qs, request):
    """Aplica filtros de búsqueda al queryset y retorna (qs, dict_filtros)."""
    q = request.GET.get('q', '').strip()
    vendedor_id = request.GET.get('vendedor', '').strip()
    estado = request.GET.get('estado', '').strip()
    fecha_desde = request.GET.get('desde', '').strip()
    fecha_hasta = request.GET.get('hasta', '').strip()

    if q:
        qs = qs.filter(
            Q(cliente__nombre__icontains=q) |
            Q(objetivo__icontains=q)
        )
    if vendedor_id:
        qs = qs.filter(vendedor_id=vendedor_id)
    if estado:
        qs = qs.filter(estado=estado)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    return qs, {
        'q': q,
        'vendedor_id': vendedor_id,
        'estado': estado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }


@login_required
@role_required('gerente', 'vendedor', 'superadmin', 'supervisor')
def lista(request):
    """
    Lista de visitas comerciales con filtros y KPIs.
    Gerente ve todas las visitas; vendedor solo las propias.
    """
    qs = _get_visitas_base(request)
    qs, filtros = _aplicar_filtros(qs, request)

    # KPIs del período filtrado
    total = qs.count()
    realizadas = qs.filter(estado='realizada').count()
    pendientes = qs.filter(estado='pendiente').count()

    # Lista de vendedores (solo para gerente en el select de filtro)
    vendedores = []
    if not request.user.is_vendedor:
        vendedores = (
            User.objects
            .filter(organization=request.org, role__in=['vendedor', 'supervisor', 'gerente'])
            .order_by('first_name', 'last_name')
        )

    context = {
        'visitas': qs,
        'total': total,
        'realizadas': realizadas,
        'pendientes': pendientes,
        'vendedores': vendedores,
        'estados': VisitaComercial.ESTADO_CHOICES,
        **filtros,
    }
    return render(request, 'visitas/lista.html', context)


@login_required
@role_required('gerente', 'vendedor', 'superadmin', 'supervisor')
def crear(request):
    """
    Crear nueva visita comercial.
    Vendedor: el campo vendedor se fija automáticamente a sí mismo.
    Gerente: puede asignar a cualquier vendedor de la org.
    """
    clientes = Cliente.objects.filter(organization=request.org, is_deleted=False).order_by('nombre')

    # Vendedores disponibles para el gerente en el select
    vendedores = []
    if not request.user.is_vendedor:
        vendedores = (
            User.objects
            .filter(organization=request.org, role__in=['vendedor', 'supervisor', 'gerente'])
            .order_by('first_name', 'last_name')
        )

    if request.method == 'POST':
        return _guardar_visita(request, clientes=clientes, vendedores=vendedores)

    context = {
        'clientes': clientes,
        'vendedores': vendedores,
        'tipos': VisitaComercial.TIPO_CHOICES,
        'estados': VisitaComercial.ESTADO_CHOICES,
        'today': timezone.now().date(),
        'modo': 'crear',
    }
    return render(request, 'visitas/form.html', context)


@login_required
@role_required('gerente', 'vendedor', 'superadmin', 'supervisor')
def editar(request, pk):
    """
    Editar visita existente.
    Vendedor solo puede editar sus propias visitas; gerente puede editar cualquiera.
    """
    visita = get_object_or_404(VisitaComercial, pk=pk, organization=request.org)

    # Vendedor solo puede editar sus propias visitas
    if request.user.is_vendedor and visita.vendedor != request.user:
        messages.error(request, 'No tienes permiso para editar esta visita.')
        return redirect('visitas:lista')

    clientes = Cliente.objects.filter(organization=request.org, is_deleted=False).order_by('nombre')
    vendedores = []
    if not request.user.is_vendedor:
        vendedores = (
            User.objects
            .filter(organization=request.org, role__in=['vendedor', 'supervisor', 'gerente'])
            .order_by('first_name', 'last_name')
        )

    if request.method == 'POST':
        return _guardar_visita(request, visita=visita, clientes=clientes, vendedores=vendedores)

    context = {
        'visita': visita,
        'clientes': clientes,
        'vendedores': vendedores,
        'tipos': VisitaComercial.TIPO_CHOICES,
        'estados': VisitaComercial.ESTADO_CHOICES,
        'modo': 'editar',
    }
    return render(request, 'visitas/form.html', context)


@login_required
@role_required('gerente', 'vendedor', 'superadmin', 'supervisor')
@require_POST
def eliminar(request, pk):
    """
    Eliminar visita. Vendedor solo puede eliminar las suyas.
    Gerente puede eliminar cualquiera.
    """
    visita = get_object_or_404(VisitaComercial, pk=pk, organization=request.org)

    if request.user.is_vendedor and visita.vendedor != request.user:
        messages.error(request, 'No tienes permiso para eliminar esta visita.')
        return redirect('visitas:lista')

    visita.delete()
    messages.success(request, 'Visita eliminada correctamente.')
    return redirect('visitas:lista')


@login_required
@role_required('gerente', 'vendedor', 'superadmin', 'supervisor')
@require_POST
def marcar_realizada(request, pk):
    """
    Marca la visita como realizada. Acepta resultado en el body del POST.
    No bloquea si el resultado está vacío.
    """
    visita = get_object_or_404(VisitaComercial, pk=pk, organization=request.org)

    if request.user.is_vendedor and visita.vendedor != request.user:
        messages.error(request, 'No tienes permiso para modificar esta visita.')
        return redirect('visitas:lista')

    resultado = request.POST.get('resultado', '').strip()
    visita.marcar_realizada(resultado=resultado)
    messages.success(request, f'Visita a {visita.cliente} marcada como realizada.')
    return redirect('visitas:lista')


# ── Lógica interna ─────────────────────────────────────────────────────────────

def _guardar_visita(request, visita=None, clientes=None, vendedores=None):
    """
    Procesa el formulario POST para crear o actualizar una visita.
    Retorna redirect en éxito o render con errores.
    """
    data = request.POST

    # Campos requeridos
    cliente_id = data.get('cliente_id', '').strip()
    fecha = data.get('fecha', '').strip()

    if not cliente_id or not fecha:
        messages.error(request, 'Cliente y fecha son campos requeridos.')
        context = {
            'visita': visita,
            'clientes': clientes,
            'vendedores': vendedores,
            'tipos': VisitaComercial.TIPO_CHOICES,
            'estados': VisitaComercial.ESTADO_CHOICES,
            'modo': 'editar' if visita else 'crear',
            'today': timezone.now().date(),
        }
        return render(request, 'visitas/form.html', context)

    # Validar cliente pertenece a la org
    cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)

    # Determinar vendedor: vendedor se fija a sí mismo; gerente puede elegir
    if request.user.is_vendedor:
        vendedor = request.user
    else:
        vendedor_id = data.get('vendedor_id', '').strip()
        if vendedor_id:
            vendedor = get_object_or_404(User, pk=vendedor_id, organization=request.org)
        else:
            vendedor = request.user

    tipo = data.get('tipo', 'presencial')
    estado = data.get('estado', 'pendiente')
    objetivo = data.get('objetivo', '').strip()
    resultado = data.get('resultado', '').strip()
    proxima_visita = data.get('proxima_visita', '').strip() or None

    if visita:
        # Actualización
        visita.cliente = cliente
        visita.vendedor = vendedor
        visita.fecha = fecha
        visita.tipo = tipo
        visita.estado = estado
        visita.objetivo = objetivo
        visita.resultado = resultado
        visita.proxima_visita = proxima_visita
        visita.save()
        messages.success(request, 'Visita actualizada correctamente.')
    else:
        # Creación
        VisitaComercial.objects.create(
            organization=request.org,
            cliente=cliente,
            vendedor=vendedor,
            fecha=fecha,
            tipo=tipo,
            estado=estado,
            objetivo=objetivo,
            resultado=resultado,
            proxima_visita=proxima_visita,
        )
        messages.success(request, 'Visita registrada correctamente.')

    return redirect('visitas:lista')
