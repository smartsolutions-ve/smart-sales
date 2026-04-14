"""Vistas del catálogo de productos."""
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import role_required
from .models import Producto, CategoriaProducto


def _producto_form_ctx(request):
    from apps.configuracion.models import UnidadMedida
    return {
        'categorias': CategoriaProducto.objects.filter(organization=request.org),
        'unidades_medida': UnidadMedida.objects.filter(organization=request.org, activa=True).order_by('tipo', 'nombre'),
    }


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
    return render(request, 'productos/form.html', _producto_form_ctx(request))


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk, organization=request.org)
    if request.method == 'POST':
        return _guardar_producto(request, producto=producto)
    return render(request, 'productos/form.html', {**_producto_form_ctx(request), 'producto': producto})


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
    """
    Endpoint JSON para autocompletar productos en el formulario de pedido.
    Acepta ?lista_precio_id=UUID para devolver precio ajustado según lista.
    """
    from decimal import Decimal
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    # Lista de precios opcional para ajustar precio_base
    lista_precio_id = request.GET.get('lista_precio_id', '').strip()
    descuento = Decimal('0')
    if lista_precio_id:
        from apps.configuracion.models import ListaPrecio
        try:
            lp = ListaPrecio.objects.get(pk=lista_precio_id, organization=request.org, activa=True)
            descuento = lp.descuento_porcentaje
        except ListaPrecio.DoesNotExist:
            pass

    from django.db.models import OuterRef, Subquery, DecimalField
    from .models import Lote

    stock_subq = (
        Lote.objects
        .filter(producto=OuterRef('pk'), is_active=True)
        .values('producto')
        .annotate(total=Sum('cantidad_disponible'))
        .values('total')
    )

    productos = (
        Producto.objects
        .filter(organization=request.org, is_active=True)
        .filter(Q(nombre__icontains=q) | Q(sku__icontains=q))
        .annotate(stock_disponible=Coalesce(
            Subquery(stock_subq, output_field=DecimalField()),
            Decimal('0')
        ))
        .values('id', 'nombre', 'sku', 'precio_base', 'unidad', 'stock_disponible')[:10]
    )

    results = []
    for p in productos:
        precio = p['precio_base']
        if precio and descuento:
            precio = (Decimal(str(precio)) * (1 - descuento / 100)).quantize(Decimal('0.01'))

        results.append({
            'id': p['id'],
            'nombre': p['nombre'],
            'sku': p['sku'] or '',
            'precio_base': str(precio) if precio else '',
            'unidad': p['unidad'] or '',
            'stock': float(p['stock_disponible'] or 0),
        })

    return JsonResponse({'results': results})


@login_required
@role_required('gerente', 'superadmin')
def alertas_stock(request):
    """Lista de productos con stock por debajo del mínimo configurado."""
    productos = (
        Producto.objects
        .filter(organization=request.org, is_active=True, stock_minimo__gt=0)
        .annotate(
            stock_actual=Coalesce(
                Sum('lotes__cantidad_disponible', filter=Q(lotes__is_active=True)),
                Decimal('0'),
            )
        )
        .filter(stock_actual__lt=F('stock_minimo'))
        .annotate(deficit=F('stock_minimo') - F('stock_actual'))
        .select_related('categoria')
        .order_by('nombre')
    )
    return render(request, 'productos/alertas_stock.html', {'productos': productos})


@login_required
@role_required('gerente', 'superadmin')
def configurar_stock_minimo(request, pk):
    """Actualiza el stock_minimo de un producto."""
    producto = get_object_or_404(Producto, pk=pk, organization=request.org)
    if request.method == 'POST':
        try:
            valor = Decimal(request.POST.get('stock_minimo', '0').replace(',', '.'))
            if valor < 0:
                raise ValueError('El valor no puede ser negativo.')
            producto.stock_minimo = valor
            producto.save(update_fields=['stock_minimo'])
            messages.success(request, f'Stock mínimo de "{producto.nombre}" actualizado a {valor}.')
        except (ValueError, Exception):
            messages.error(request, 'Valor inválido. Ingrese un número positivo.')
    return redirect('productos:alertas_stock')


def _guardar_producto(request, producto):
    data = request.POST
    nombre = data.get('nombre', '').strip()
    sku = data.get('sku', '').strip()
    descripcion = data.get('descripcion', '').strip()
    precio_base = data.get('precio_base', '').strip() or None
    peso_kg = data.get('peso_kg', '').strip() or None
    unidad = data.get('unidad', '').strip()
    unidad_medida_id = data.get('unidad_medida_id', '').strip() or None
    categoria_id = data.get('categoria_id', '').strip() or None
    is_active = data.get('is_active') == 'on'
    exento_iva = data.get('exento_iva') == 'on'

    if not nombre:
        messages.error(request, 'El nombre del producto es requerido.')
        return render(request, 'productos/form.html', {**_producto_form_ctx(request), 'producto': producto})

    # Verificar SKU único (por org), ignorando el producto actual en edición
    if sku:
        qs = Producto.objects.filter(organization=request.org, sku=sku)
        if producto:
            qs = qs.exclude(pk=producto.pk)
        if qs.exists():
            messages.error(request, f'Ya existe un producto con el SKU "{sku}".')
            return render(request, 'productos/form.html', {**_producto_form_ctx(request), 'producto': producto})

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
    if unidad_medida_id:
        from apps.configuracion.models import UnidadMedida
        producto.unidad_medida = UnidadMedida.objects.filter(pk=unidad_medida_id, organization=request.org).first()
    else:
        producto.unidad_medida = None
    producto.categoria = categoria
    producto.is_active = is_active
    producto.exento_iva = exento_iva

    stock_minimo_val = data.get('stock_minimo', '0').strip() or '0'
    try:
        producto.stock_minimo = Decimal(stock_minimo_val)
    except Exception:
        producto.stock_minimo = Decimal('0')

    producto.save()

    messages.success(request, f'Producto "{producto.nombre}" guardado.')
    return redirect('productos:lista')
