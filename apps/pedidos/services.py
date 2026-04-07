from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Pedido, PedidoItem
from .utils import generar_numero_pedido

class PedidoService:
    @staticmethod
    def guardar_pedido(
        organization,
        user,
        cliente,
        vendedor,
        fecha_pedido,
        items_data,
        fecha_entrega=None,
        estado='Pendiente',
        observaciones='',
        ref_competencia='',
        pedido_existente=None,
        metodo_pago=None,
        zona_despacho=None,
    ):
        """
        Crea o actualiza un pedido con sus items de forma atómica.
        Retorna el pedido guardado.
        Lanza ValidationError si hay inconsistencias.
        """
        if not items_data:
            raise ValidationError('El pedido debe tener al menos un ítem.')

        es_nuevo = pedido_existente is None

        with transaction.atomic():
            if es_nuevo:
                pedido = Pedido(
                    organization=organization,
                    numero=generar_numero_pedido(organization),
                    created_by=user,
                )
            else:
                pedido = pedido_existente

            pedido.cliente = cliente
            pedido.vendedor = vendedor
            pedido.fecha_pedido = fecha_pedido
            pedido.fecha_entrega = fecha_entrega
            pedido.estado = estado
            pedido.observaciones = observaciones
            pedido.ref_competencia = ref_competencia
            pedido.metodo_pago = metodo_pago
            pedido.zona_despacho = zona_despacho
            pedido.save()

            if not es_nuevo:
                estado_anterior = Pedido.objects.get(pk=pedido_existente.pk).estado
                pedido.items.all().delete()
            else:
                estado_anterior = 'Pendiente'

            from apps.productos.models import Producto
            from decimal import Decimal
            skus = [item['sku'] for item in items_data if item.get('sku')]
            productos_db = {p.sku: p for p in Producto.objects.filter(sku__in=skus, organization=organization)}

            items_a_crear = []
            for item_data in items_data:
                exento = True
                monto_iva = Decimal('0.00')
                if item_data.get('sku') in productos_db:
                    prod = productos_db[item_data['sku']]
                    exento = prod.exento_iva
                if not exento:
                    subtotal_item = Decimal(str(item_data['cantidad'])) * Decimal(str(item_data['precio']))
                    monto_iva = subtotal_item * Decimal('0.16')
                    
                items_a_crear.append(PedidoItem(
                    pedido=pedido,
                    organization=pedido.organization,
                    exento_iva=exento,
                    monto_iva=monto_iva,
                    **item_data
                ))

            PedidoItem.objects.bulk_create(items_a_crear)

            pedido.recalcular_total()

            # Descontar stock si transiciona a Confirmado/En Proceso/Entregado desde Pendiente / Cancelado
            estados_con_stock_descontado = ['Confirmado', 'En Proceso', 'Entregado']
            if estado in estados_con_stock_descontado and estado_anterior not in estados_con_stock_descontado:
                PedidoService.procesar_descuento_stock(pedido, user)

            # Auditoría
            from .audit import log_pedido
            accion = 'creado' if es_nuevo else 'editado'
            log_pedido(pedido, user, accion, f'Cliente: {cliente}, Total: ${pedido.total}')

        return pedido

    @staticmethod
    def procesar_descuento_stock(pedido, user=None):
        """
        Aplica metodología FEFO para descontar el stock cuando el pedido es confirmado.
        """
        from apps.productos.models import Producto, MovimientoInventario

        for item in pedido.items.all():
            if not item.sku:
                continue
            try:
                producto = Producto.objects.get(sku=item.sku, organization=pedido.organization)
            except Producto.DoesNotExist:
                continue
            
            lotes = producto.lotes.filter(cantidad_disponible__gt=0, is_active=True).order_by('fecha_caducidad')
            
            cantidad_restante = item.cantidad
            for lote in lotes:
                if cantidad_restante <= 0:
                    break
                
                descontar = min(cantidad_restante, lote.cantidad_disponible)
                lote.cantidad_disponible -= descontar
                lote.save()
                cantidad_restante -= descontar
                
                MovimientoInventario.objects.create(
                    lote=lote,
                    tipo='SALIDA',
                    cantidad=-descontar,
                    referencia=f'Pedido {pedido.numero}',
                    created_by=user
                )
            
            if cantidad_restante > 0:
                raise ValidationError(f'No hay suficiente stock para {item.producto}. Faltan {cantidad_restante}.')

