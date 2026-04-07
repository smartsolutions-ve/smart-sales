"""Vistas del panel de superadmin de SmartSales."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Sum, Q
from django.utils import timezone

from apps.accounts.decorators import superadmin_required
from .models import Organization, User


@superadmin_required
def index(request):
    """Dashboard del superadmin con KPIs globales."""
    orgs = Organization.objects.annotate(
        users_count=Count('user', filter=Q(user__is_active=True)),
    ).order_by('-created_at')

    total_orgs = orgs.count()
    orgs_activas = orgs.filter(is_active=True).count()
    context = {
        'orgs': orgs,
        'total_orgs': total_orgs,
        'orgs_activas': orgs_activas,
        'orgs_suspendidas': total_orgs - orgs_activas,
    }
    return render(request, 'admin_panel/index.html', context)


@superadmin_required
def org_lista(request):
    hoy = timezone.now()
    orgs = Organization.objects.annotate(
        users_count=Count('user', filter=Q(user__is_active=True), distinct=True),
        pedidos_mes=Count(
            'pedido',
            filter=Q(
                pedido__fecha_pedido__year=hoy.year,
                pedido__fecha_pedido__month=hoy.month,
            ),
            distinct=True,
        ),
    ).order_by('-created_at')
    return render(request, 'admin_panel/org_lista.html', {'orgs': orgs})


@superadmin_required
@require_http_methods(['GET', 'POST'])
def org_crear(request):
    if request.method == 'POST':
        return _guardar_org(request, org=None)
    return render(request, 'admin_panel/org_form.html', {'planes': Organization.PLANES})


@superadmin_required
def org_detalle(request, pk):
    from apps.pedidos.models import Pedido
    org = get_object_or_404(Organization, pk=pk)
    usuarios = org.user_set.filter(is_active=True).order_by('role', 'first_name')
    hoy = timezone.now()

    pedidos_qs = Pedido.objects.filter(organization=org)
    pedidos_mes = pedidos_qs.filter(
        fecha_pedido__year=hoy.year,
        fecha_pedido__month=hoy.month,
    )
    stats = pedidos_mes.aggregate(
        total_pedidos=Count('id'),
        total_ventas=Sum('total'),
    )
    total_pedidos_historico = pedidos_qs.count()

    context = {
        'org': org,
        'usuarios': usuarios,
        'pedidos_mes': stats['total_pedidos'] or 0,
        'ventas_mes': stats['total_ventas'] or 0,
        'total_pedidos': total_pedidos_historico,
    }
    return render(request, 'admin_panel/org_detalle.html', context)


@superadmin_required
@require_POST
def org_toggle_activa(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    org.is_active = not org.is_active
    org.save(update_fields=['is_active'])
    estado = 'activada' if org.is_active else 'desactivada'
    messages.success(request, f'Organización "{org.name}" {estado}.')
    return redirect('admin_panel:org_detalle', pk=org.pk)


@superadmin_required
def org_usuarios(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    usuarios = org.user_set.order_by('role', 'first_name')
    return render(request, 'admin_panel/org_usuarios.html', {'org': org, 'usuarios': usuarios})


@superadmin_required
@require_http_methods(['GET', 'POST'])
def usuario_crear(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    if request.method == 'POST':
        return _guardar_usuario(request, org)
    roles = [r for r in User.ROLES if r[0] != 'superadmin']
    return render(request, 'admin_panel/usuario_form.html', {'org': org, 'roles': roles})


def _guardar_org(request, org):
    data = request.POST
    name = data.get('name', '').strip()
    slug = data.get('slug', '').strip()
    plan = data.get('plan', 'starter')

    if not name or not slug:
        messages.error(request, 'Nombre y slug son requeridos.')
        return render(request, 'admin_panel/org_form.html', {'planes': Organization.PLANES})

    if org is None:
        org = Organization(name=name, slug=slug, plan=plan)
    else:
        org.name = name
        org.slug = slug
        org.plan = plan

    org.save()
    messages.success(request, f'Organización "{org.name}" guardada.')
    return redirect('admin_panel:org_detalle', pk=org.pk)


def _guardar_usuario(request, org):
    data = request.POST
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    role = data.get('role', 'vendedor')
    password = data.get('password', '').strip()

    if not username or not password:
        messages.error(request, 'Usuario y contraseña son requeridos.')
        roles = [r for r in User.ROLES if r[0] != 'superadmin']
        return render(request, 'admin_panel/usuario_form.html', {'org': org, 'roles': roles})

    if User.objects.filter(username=username).exists():
        messages.error(request, f'El usuario "{username}" ya existe.')
        roles = [r for r in User.ROLES if r[0] != 'superadmin']
        return render(request, 'admin_panel/usuario_form.html', {'org': org, 'roles': roles})

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        organization=org,
        role=role,
    )
    messages.success(request, f'Usuario "{user.username}" creado en {org.name}.')
    return redirect('admin_panel:org_usuarios', pk=org.pk)


@superadmin_required
@require_http_methods(['GET', 'POST'])
def org_editar(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    if request.method == 'POST':
        return _guardar_org(request, org=org)
    return render(request, 'admin_panel/org_form.html', {
        'org': org,
        'planes': Organization.PLANES,
    })


@superadmin_required
@require_http_methods(['GET', 'POST'])
def usuario_editar(request, org_pk, user_pk):
    org = get_object_or_404(Organization, pk=org_pk)
    usuario = get_object_or_404(User, pk=user_pk, organization=org)
    if request.method == 'POST':
        data = request.POST
        usuario.first_name = data.get('first_name', '').strip()
        usuario.last_name = data.get('last_name', '').strip()
        usuario.email = data.get('email', '').strip()
        role = data.get('role', 'vendedor')
        if role != 'superadmin':
            usuario.role = role
        usuario.is_active = data.get('is_active') == 'on'
        usuario.save(update_fields=['first_name', 'last_name', 'email', 'role', 'is_active'])
        messages.success(request, f'Usuario "{usuario.username}" actualizado.')
        return redirect('admin_panel:org_usuarios', pk=org.pk)

    roles = [r for r in User.ROLES if r[0] != 'superadmin']
    return render(request, 'admin_panel/usuario_form.html', {
        'org': org,
        'usuario': usuario,
        'roles': roles,
    })


@superadmin_required
@require_POST
def usuario_eliminar(request, org_pk, user_pk):
    org = get_object_or_404(Organization, pk=org_pk)
    usuario = get_object_or_404(User, pk=user_pk, organization=org)
    username = usuario.username
    usuario.delete()
    messages.success(request, f'Usuario "{username}" eliminado.')
    return redirect('admin_panel:org_usuarios', pk=org.pk)


@superadmin_required
@require_http_methods(['GET', 'POST'])
def usuario_cambiar_password(request, org_pk, user_pk):
    org = get_object_or_404(Organization, pk=org_pk)
    usuario = get_object_or_404(User, pk=user_pk, organization=org)
    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()
        if not password:
            messages.error(request, 'La contraseña no puede estar vacía.')
        elif password != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        else:
            usuario.set_password(password)
            usuario.save(update_fields=['password'])
            messages.success(request, f'Contraseña de "{usuario.username}" actualizada.')
            return redirect('admin_panel:org_usuarios', pk=org.pk)

    return render(request, 'admin_panel/usuario_password.html', {
        'org': org,
        'usuario': usuario,
    })
