"""Vistas del catálogo de productos."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import role_required
from .models import Producto, CategoriaProducto


@login_required
@role_required('gerente', 'superadmin')
def lista(request):
    q = request.GET.get('q', '')
    categoria_id = request.GET.get('categoria', '')
    solo_activos = request.GET.get('activos', 'true') != 'false'

    productos = (
        Producto.objects
        .filter(organization=request.org)
        .select_related('categoria')
        .order_by('nombre')
    )
    if q:
        from django.db.models import Q
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(sku__icontains=q)
        )
    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)
    if solo_activos:
        productos = productos.filter(is_active=True)

    categorias = CategoriaProducto.objects.filter(organization=request.org)

    context = {
        'productos': productos,
        'categorias': categorias,
        'q': q,
        'categoria_filtro': categoria_id,
        'solo_activos': solo_activos,
    }
    return render(request, 'productos/lista.html', context)


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def crear(request):
    if request.method == 'POST':
        return _guardar_producto(request, producto=None)
    categorias = CategoriaProducto.objects.filter(organization=request.org)
    return render(request, 'productos/form.html', {'categorias': categorias})


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk, organization=request.org)
    if request.method == 'POST':
        return _guardar_producto(request, producto=producto)
    categorias = CategoriaProducto.objects.filter(organization=request.org)
    return render(request, 'productos/form.html', {'producto': producto, 'categorias': categorias})


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk, organization=request.org)
    nombre = producto.nombre
    producto.is_active = False
    producto.save(update_fields=['is_active'])
    messages.success(request, f'Producto "{nombre}" desactivado.')
    return redirect('productos:lista')


@login_required
def buscar_json(request):
    """Endpoint JSON para autocompletar productos en el formulario de pedido."""
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    productos = (
        Producto.objects
        .filter(organization=request.org, is_active=True)
        .filter(Q(nombre__icontains=q) | Q(sku__icontains=q))
        .values('id', 'nombre', 'sku', 'precio_base', 'unidad')[:10]
    )

    results = [
        {
            'id': p['id'],
            'nombre': p['nombre'],
            'sku': p['sku'] or '',
            'precio_base': str(p['precio_base']) if p['precio_base'] else '',
            'unidad': p['unidad'] or '',
        }
        for p in productos
    ]
    return JsonResponse({'results': results})


def _guardar_producto(request, producto):
    data = request.POST
    nombre = data.get('nombre', '').strip()
    sku = data.get('sku', '').strip()
    descripcion = data.get('descripcion', '').strip()
    precio_base = data.get('precio_base', '').strip() or None
    peso_kg = data.get('peso_kg', '').strip() or None
    unidad = data.get('unidad', '').strip()
    categoria_id = data.get('categoria_id', '').strip() or None
    is_active = data.get('is_active') == 'on'

    if not nombre:
        messages.error(request, 'El nombre del producto es requerido.')
        categorias = CategoriaProducto.objects.filter(organization=request.org)
        return render(request, 'productos/form.html', {'producto': producto, 'categorias': categorias})

    # Verificar SKU único (por org), ignorando el producto actual en edición
    if sku:
        qs = Producto.objects.filter(organization=request.org, sku=sku)
        if producto:
            qs = qs.exclude(pk=producto.pk)
        if qs.exists():
            messages.error(request, f'Ya existe un producto con el SKU "{sku}".')
            categorias = CategoriaProducto.objects.filter(organization=request.org)
            return render(request, 'productos/form.html', {'producto': producto, 'categorias': categorias})

    categoria = None
    if categoria_id:
        categoria = get_object_or_404(CategoriaProducto, pk=categoria_id, organization=request.org)

    if producto is None:
        producto = Producto(organization=request.org)

    producto.nombre = nombre
    producto.sku = sku
    producto.descripcion = descripcion
    producto.precio_base = precio_base
    producto.peso_kg = peso_kg
    producto.unidad = unidad
    producto.categoria = categoria
    producto.is_active = is_active
    producto.save()

    messages.success(request, f'Producto "{producto.nombre}" guardado.')
    return redirect('productos:lista')
