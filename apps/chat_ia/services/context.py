"""Construye el contexto de la BD para inyectar al LLM."""
from datetime import timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone


def build_context_for_org(org):
    """Construye un resumen textual de los datos de la organización."""
    if org is None:
        return (
            'No hay organización seleccionada. '
            'El chat IA requiere acceder como gerente de una organización.'
        )

    from apps.pedidos.models import Pedido, Cliente, Factura
    from apps.productos.models import Producto
    from apps.competencia.models import CompetenciaRegistro
    from apps.flotas.models import Vehiculo, Viaje
    from apps.cuotas.models import VentaMensual, TasaCambio

    ahora = timezone.now()
    hoy = ahora.date()
    mes_actual = hoy.replace(day=1)

    parts = []

    # ── Sección 1: Resumen ejecutivo ──
    pedidos = Pedido.objects.filter(organization=org)
    total_pedidos = pedidos.count()
    por_estado = dict(
        pedidos.values_list('estado')
        .annotate(c=Count('id'))
        .values_list('estado', 'c')
    )
    por_despacho = dict(
        pedidos.values_list('estado_despacho')
        .annotate(c=Count('id'))
        .values_list('estado_despacho', 'c')
    )

    total_clientes = Cliente.objects.filter(organization=org).count()
    total_productos = Producto.objects.filter(organization=org, is_active=True).count()

    ventas_mes = pedidos.filter(
        fecha_pedido__gte=mes_actual
    ).exclude(estado='Cancelado').aggregate(total=Sum('total'))['total'] or 0

    parts.append(f"""=== RESUMEN EJECUTIVO ===
Fecha y hora actual: {ahora:%d/%m/%Y %H:%M}
Total pedidos (todos): {total_pedidos}
  - Pendientes: {por_estado.get('Pendiente', 0)}
  - Confirmados: {por_estado.get('Confirmado', 0)}
  - En Proceso: {por_estado.get('En Proceso', 0)}
  - Entregados: {por_estado.get('Entregado', 0)}
  - Cancelados: {por_estado.get('Cancelado', 0)}
Total clientes: {total_clientes}
Total productos activos: {total_productos}
Despachos pendientes: {por_despacho.get('Pendiente Despacho', 0)}
Despachos en tránsito: {por_despacho.get('En Tránsito', 0)}
Ventas del mes actual (no cancelados): ${ventas_mes:,.2f}""")

    # ── Facturación ──
    pedidos_no_cancel = pedidos.exclude(estado='Cancelado').filter(total__gt=0)
    pedidos_con_fact = pedidos_no_cancel.annotate(
        total_facturado=Sum('facturas__monto')
    )
    sin_facturar = pedidos_con_fact.filter(
        Q(total_facturado__isnull=True) | Q(total_facturado=0)
    )
    monto_sin_facturar = sin_facturar.aggregate(t=Sum('total'))['t'] or 0

    parcial = pedidos_con_fact.filter(
        total_facturado__gt=0, total_facturado__lt=models_F('total')
    ) if False else pedidos_con_fact.exclude(
        Q(total_facturado__isnull=True) | Q(total_facturado=0)
    ).extra(where=['COALESCE((SELECT SUM(monto) FROM pedidos_factura WHERE pedidos_factura.pedido_id = pedidos_pedido.id), 0) < pedidos_pedido.total'])
    # Simplificado: contamos directamente
    from django.db.models import F as models_F, DecimalField
    from django.db.models.functions import Coalesce

    pedidos_annotated = pedidos_no_cancel.annotate(
        total_fact=Coalesce(Sum('facturas__monto'), 0, output_field=DecimalField())
    )
    n_sin_facturar = pedidos_annotated.filter(total_fact=0).count()
    n_parcial = pedidos_annotated.filter(total_fact__gt=0, total_fact__lt=models_F('total')).count()
    n_facturado = pedidos_annotated.filter(total_fact__gte=models_F('total')).count()

    facturado_mes = Factura.objects.filter(
        pedido__organization=org,
        fecha_factura__gte=mes_actual,
    ).aggregate(total=Sum('monto'))['total'] or 0

    parts.append(f"""
--- Facturación ---
Pedidos sin facturar: {n_sin_facturar} (monto total: ${monto_sin_facturar:,.2f})
Pedidos con facturación parcial: {n_parcial}
Pedidos totalmente facturados: {n_facturado}
Monto facturado mes actual: ${facturado_mes:,.2f}""")

    # ── Flotas ──
    vehiculos_activos = Vehiculo.objects.filter(organization=org, is_active=True).count()
    viajes = Viaje.objects.filter(organization=org)
    viajes_programados = viajes.filter(estado='Programado').count()
    viajes_en_ruta = viajes.filter(estado='En Ruta').count()
    viajes_completados_mes = viajes.filter(estado='Completado', fecha__gte=mes_actual).count()
    costo_fletes_mes = viajes.filter(
        estado='Completado', fecha__gte=mes_actual
    ).aggregate(total=Sum('costo_flete'))['total'] or 0

    parts.append(f"""
--- Flotas ---
Vehículos activos: {vehiculos_activos}
Viajes programados: {viajes_programados}
Viajes en ruta: {viajes_en_ruta}
Viajes completados (mes): {viajes_completados_mes}
Costo fletes mes: ${costo_fletes_mes:,.2f}""")

    # ── Cuotas ──
    ultimo_periodo = VentaMensual.objects.filter(
        organization=org
    ).order_by('-periodo').values_list('periodo', flat=True).first()

    if ultimo_periodo:
        ventas_periodo = VentaMensual.objects.filter(
            organization=org, periodo=ultimo_periodo)
        totales_cuota = ventas_periodo.aggregate(
            plan=Sum('plan_venta_usd'), real=Sum('real_venta_usd'))
        plan_t = float(totales_cuota['plan'] or 0)
        real_t = float(totales_cuota['real'] or 0)
        cumpl_global = round(real_t / plan_t * 100, 1) if plan_t else 0

        parts.append(f"""
--- Cuotas y Ventas ---
Último periodo: {ultimo_periodo:%Y-%m}
Cumplimiento global: {cumpl_global}% (Plan: ${plan_t:,.2f} / Real: ${real_t:,.2f})""")
    else:
        parts.append('\n--- Cuotas y Ventas ---\n[Sin datos de cuotas]')

    tasa = TasaCambio.objects.filter(organization=org).first()
    if tasa:
        parts.append(f'Tasa de cambio: {tasa.tasa_bs_por_usd} Bs/USD ({tasa.fuente}, {tasa.fecha:%d/%m/%Y})')

    # ── Sección 2: Pedidos recientes ──
    recientes = pedidos.select_related('cliente', 'vendedor').order_by('-fecha_pedido', '-created_at')[:20]
    if recientes:
        lines = ['\n=== ÚLTIMOS 20 PEDIDOS ===']
        for p in recientes:
            vendedor_name = p.vendedor.get_full_name() or p.vendedor.username
            lines.append(
                f'- {p.numero} | Cliente: {p.cliente.nombre} | '
                f'Vendedor: {vendedor_name} | Estado: {p.estado} | '
                f'Despacho: {p.estado_despacho} | Fecha: {p.fecha_pedido:%d/%m/%Y} | '
                f'Total: ${p.total:,.2f}'
            )
        parts.append('\n'.join(lines))
    else:
        parts.append('\n=== ÚLTIMOS 20 PEDIDOS ===\n[Sin datos]')

    # ── Sección 3: Top clientes ──
    top_clientes = (
        Cliente.objects.filter(organization=org)
        .annotate(
            num_pedidos=Count('pedido', filter=~Q(pedido__estado='Cancelado')),
            total_compras=Sum('pedido__total', filter=~Q(pedido__estado='Cancelado')),
        )
        .filter(num_pedidos__gt=0)
        .order_by('-total_compras')[:10]
    )
    if top_clientes:
        lines = ['\n=== TOP 10 CLIENTES POR COMPRAS ===']
        for i, c in enumerate(top_clientes, 1):
            lines.append(f'{i}. {c.nombre} — {c.num_pedidos} pedidos — Total: ${c.total_compras:,.2f}')
        parts.append('\n'.join(lines))

    # ── Sección 4: Top productos ──
    from apps.pedidos.models import PedidoItem
    top_productos = (
        PedidoItem.objects.filter(pedido__organization=org)
        .exclude(pedido__estado='Cancelado')
        .values('producto')
        .annotate(
            total_cantidad=Sum('cantidad'),
            total_venta=Sum(models_F('cantidad') * models_F('precio'), output_field=DecimalField()),
        )
        .order_by('-total_cantidad')[:10]
    )
    if top_productos:
        lines = ['\n=== TOP 10 PRODUCTOS MÁS VENDIDOS ===']
        for i, p in enumerate(top_productos, 1):
            lines.append(f'{i}. {p["producto"]} — {p["total_cantidad"]} uds — ${p["total_venta"]:,.2f}')
        parts.append('\n'.join(lines))

    # ── Sección 4.5: Top productos pendientes de despacho ──
    pendientes_despacho = (
        PedidoItem.objects.filter(
            pedido__organization=org,
            pedido__estado_despacho='Pendiente Despacho'
        )
        .exclude(pedido__estado='Cancelado')
        .values('producto')
        .annotate(
            total_cantidad=Sum('cantidad'),
        )
        .order_by('-total_cantidad')[:10]
    )
    if pendientes_despacho:
        lines = ['\n=== TOP 10 PRODUCTOS PENDIENTES DE DESPACHO ===']
        for i, p in enumerate(pendientes_despacho, 1):
            lines.append(f'{i}. {p["producto"]} — {p["total_cantidad"]} uds en espera')
        parts.append('\n'.join(lines))

    # ── Sección 5: Competencia ──
    competencia = (
        CompetenciaRegistro.objects.filter(organization=org)
        .select_related('vendedor')
        .order_by('-fecha')[:10]
    )
    if competencia:
        lines = ['\n=== INTELIGENCIA DE COMPETENCIA (últimos 10) ===']
        for c in competencia:
            diff = c.diferencia_precio
            caro = '(somos más caros)' if c.somos_mas_caros else '(somos más baratos)'
            lines.append(
                f'- {c.fecha:%d/%m/%Y} | Producto: {c.producto} | '
                f'Competidor: {c.competidor} | Su precio: ${c.precio_comp} | '
                f'Nuestro: ${c.precio_nuestro} | Dif: ${diff} {caro}'
            )
        parts.append('\n'.join(lines))

    # ── Sección 6: Alertas ──
    alertas = ['\n=== ALERTAS ACTIVAS ===']
    has_alertas = False

    # Pedidos vencidos
    vencidos = pedidos.filter(
        fecha_entrega__lt=hoy
    ).exclude(
        estado__in=['Entregado', 'Cancelado']
    ).select_related('cliente')[:5]
    if vencidos:
        has_alertas = True
        alertas.append(f'⚠ Pedidos vencidos (fecha entrega pasada): {vencidos.count()}')
        for p in vencidos:
            alertas.append(f'  - {p.numero} | {p.cliente.nombre} | Vencido: {p.fecha_entrega:%d/%m/%Y} | ${p.total:,.2f}')

    # Pedidos estancados en despacho
    hace_3_dias = hoy - timedelta(days=3)
    estancados = pedidos.filter(
        estado_despacho='Pendiente Despacho',
        fecha_pedido__lte=hace_3_dias,
    ).exclude(estado__in=['Entregado', 'Cancelado']).select_related('cliente')[:5]
    if estancados:
        has_alertas = True
        alertas.append(f'⚠ Pedidos sin mover en despacho (>3 días): {estancados.count()}')
        for p in estancados:
            alertas.append(f'  - {p.numero} | {p.cliente.nombre} | Sin mover desde: {p.fecha_pedido:%d/%m/%Y}')

    # Pedidos con alto monto sin facturar
    alto_sin_fact = pedidos_annotated.filter(
        total_fact=0, total__gte=5000
    ).exclude(estado='Cancelado').select_related('cliente')[:5]
    if alto_sin_fact:
        has_alertas = True
        alertas.append(f'⚠ Pedidos con alto monto sin facturar (>$5,000): {alto_sin_fact.count()}')
        for p in alto_sin_fact:
            alertas.append(f'  - {p.numero} | {p.cliente.nombre} | Total: ${p.total:,.2f}')

    if not has_alertas:
        alertas.append('Sin alertas activas.')

    parts.append('\n'.join(alertas))

    # ── Sección 7: Facturas recientes ──
    facturas_recientes = Factura.objects.filter(
        pedido__organization=org
    ).select_related('pedido', 'pedido__cliente').order_by('-fecha_factura')[:10]
    if facturas_recientes:
        lines = ['\n=== ÚLTIMAS 10 FACTURAS ===']
        for f in facturas_recientes:
            lines.append(
                f'- {f.numero_factura} | Pedido: {f.pedido.numero} | '
                f'Cliente: {f.pedido.cliente.nombre} | '
                f'Fecha: {f.fecha_factura:%d/%m/%Y} | Monto: ${f.monto:,.2f}'
            )
        parts.append('\n'.join(lines))

    # ── Sección 8: Flotas ──
    vehiculos_lista = Vehiculo.objects.filter(
        organization=org, is_active=True
    ).select_related('chofer_habitual')[:10]
    if vehiculos_lista:
        lines = ['\n=== FLOTA DE VEHÍCULOS ===']
        for v in vehiculos_lista:
            chofer = v.chofer_habitual.get_full_name() if v.chofer_habitual else 'Sin chofer'
            lines.append(f'- {v.placa} | {v.marca} {v.modelo} | Capacidad: {v.capacidad_kg} kg | Chofer: {chofer}')
        parts.append('\n'.join(lines))

    viajes_recientes = viajes.select_related(
        'vehiculo', 'chofer'
    ).annotate(
        total_peso=Sum('detalles__peso_estimado_kg'),
        total_pedidos=Count('detalles'),
    ).order_by('-fecha')[:10]
    if viajes_recientes:
        lines = ['\n=== ÚLTIMOS 10 VIAJES ===']
        for v in viajes_recientes:
            peso = v.total_peso or 0
            pct = round(float(peso) / float(v.vehiculo.capacidad_kg) * 100, 1) if v.vehiculo.capacidad_kg and peso else 0
            chofer = v.chofer.get_full_name() or v.chofer.username
            costo = f'${v.costo_flete:,.2f}' if v.costo_flete else '—'
            lines.append(
                f'- {v.fecha:%d/%m/%Y} | Vehículo: {v.vehiculo.placa} | Chofer: {chofer} | '
                f'Estado: {v.estado} | Pedidos: {v.total_pedidos} | '
                f'Peso: {peso} kg ({pct}%) | Costo: {costo}'
            )
        parts.append('\n'.join(lines))

    # ── Sección 9: Cuotas detalladas ──
    if ultimo_periodo:
        ventas_periodo = VentaMensual.objects.filter(
            organization=org, periodo=ultimo_periodo)

        por_zona = (
            ventas_periodo.values('zona_nombre')
            .annotate(plan=Sum('plan_venta_usd'), real=Sum('real_venta_usd'))
            .order_by('-real')
        )
        if por_zona:
            lines = [f'\n=== CUOTAS Y VENTAS — {ultimo_periodo:%Y-%m} ===\nPor Zona:']
            for z in por_zona:
                p_val = float(z['plan'] or 0)
                r_val = float(z['real'] or 0)
                cumpl = round(r_val / p_val * 100, 1) if p_val else 0
                lines.append(f'- {z["zona_nombre"] or "Sin zona"} | Plan: ${p_val:,.2f} | Real: ${r_val:,.2f} | {cumpl}%')
            parts.append('\n'.join(lines))

        por_vendedor = (
            ventas_periodo.values('vendedor_nombre')
            .annotate(plan=Sum('plan_venta_usd'), real=Sum('real_venta_usd'))
            .order_by('-real')[:5]
        )
        if por_vendedor:
            lines = ['\nTop 5 Vendedores por venta:']
            for i, v in enumerate(por_vendedor, 1):
                p_val = float(v['plan'] or 0)
                r_val = float(v['real'] or 0)
                cumpl = round(r_val / p_val * 100, 1) if p_val else 0
                lines.append(f'{i}. {v["vendedor_nombre"]} | Plan: ${p_val:,.2f} | Real: ${r_val:,.2f} | {cumpl}%')
            parts.append('\n'.join(lines))

    # ── Truncar si excede el límite ──
    result = '\n'.join(parts)
    if len(result) > 24000:
        result = result[:24000] + '\n\n[Contexto truncado por límite de tamaño]'

    return result
