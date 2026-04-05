import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import Organization, User
from apps.productos.models import CategoriaProducto, Producto, Lote, MovimientoInventario
from apps.pedidos.models import Cliente, Pedido, PedidoItem
from apps.flotas.models import Vehiculo, Viaje, ViajeDetalle

class Command(BaseCommand):
    help = 'Carga datos de prueba robustos para MegaConfites Occidente C.A.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando carga de datos para MegaConfites...')

        # 1. Organización
        org, _ = Organization.objects.get_or_create(
            name='Distribuidora MegaConfites Occidente, C.A.',
            defaults={'slug': 'megaconfites-occ', 'plan': 'pro'}
        )

        # 2. Usuarios
        gerente, _ = User.objects.get_or_create(username='gerente_mega', defaults={
            'email': 'gerente@megaconfites.com', 'first_name': 'Carlos', 'last_name': 'Mendoza',
            'role': 'gerente', 'organization': org
        })
        gerente.set_password('Mega2026*')
        gerente.save()

        supervisor, _ = User.objects.get_or_create(username='supervisor_mega', defaults={
            'email': 'supervisor@megaconfites.com', 'first_name': 'Ana', 'last_name': 'Silva',
            'role': 'supervisor', 'organization': org
        })
        supervisor.set_password('Mega2026*')
        supervisor.save()

        vendedor1, _ = User.objects.get_or_create(username='vendedor_mega1', defaults={
            'email': 'vendedor1@megaconfites.com', 'first_name': 'Pedro', 'last_name': 'Pérez',
            'role': 'vendedor', 'organization': org, 'supervisor_asignado': supervisor
        })
        vendedor1.set_password('Mega2026*')
        vendedor1.save()

        chofer1, _ = User.objects.get_or_create(username='chofer_mega', defaults={
            'email': 'chofer@megaconfites.com', 'first_name': 'Luis', 'last_name': 'Camacho',
            'role': 'vendedor', 'organization': org # Chofer acts internally
        })
        chofer1.set_password('Mega2026*')
        chofer1.save()

        # 3. Vehículos
        npr_pesado, _ = Vehiculo.objects.get_or_create(placa='A12B34C', organization=org, defaults={
            'marca': 'Chevrolet', 'modelo': 'NPR', 'capacidad_kg': Decimal('5000.00'), 'chofer_habitual': chofer1
        })

        # 4. Clientes B2B
        clientes_data = [
            {'nombre': 'Supermercados Euromart', 'tipo': 'Cadena'},
            {'nombre': 'Abasto La Esperanza', 'tipo': 'Abasto'},
            {'nombre': 'Farmacia Alemana', 'tipo': 'Farmacia'},
            {'nombre': 'Panadería Reina', 'tipo': 'Panadería'},
            {'nombre': 'Bodegón Express M&M', 'tipo': 'Bodegón'}
        ]
        
        clientes = []
        for cd in clientes_data:
            cliente, _ = Cliente.objects.get_or_create(
                organization=org, nombre=cd['nombre'],
                defaults={'contacto': f'Gerente de {cd["tipo"]}', 'telefono': '0414-0000000'}
            )
            clientes.append(cliente)

        # 5. Categorías y Productos Mayoristas
        cat_viveres, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Víveres Básicos')
        cat_enlatados, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Enlatados y Salsas')
        cat_lacteos, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Lácteos y Repostería')
        cat_bebidas, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Bebidas')

        productos_data = [
            {'nombre': 'Caraotas Negras Pantera', 'sku': 'PAN-CAR-01', 'categoria': cat_viveres, 'precio': '30.00', 'peso': '24.0', 'unidad': 'Bulto 24kg'},
            {'nombre': 'Pasta Corta Galo', 'sku': 'GAL-PC-01', 'categoria': cat_viveres, 'precio': '15.50', 'peso': '12.0', 'unidad': 'Caja 12kg'},
            {'nombre': 'Melocotones Del Monte', 'sku': 'DEL-MEL-01', 'categoria': cat_enlatados, 'precio': '45.00', 'peso': '15.0', 'unidad': 'Caja 12 Lt'},
            {'nombre': 'Salsa de Ajo De Campo', 'sku': 'CAM-AJO-01', 'categoria': cat_enlatados, 'precio': '12.00', 'peso': '6.0', 'unidad': 'Display 12 und'},
            {'nombre': 'Leche Lumalac', 'sku': 'LUM-LEC-01', 'categoria': cat_lacteos, 'precio': '60.00', 'peso': '25.0', 'unidad': 'Saco 25kg'},
            {'nombre': 'Refresco Glup! Cola', 'sku': 'GLU-COL-01', 'categoria': cat_bebidas, 'precio': '18.00', 'peso': '20.0', 'unidad': 'Paca 6 und'},
        ]

        productos = []
        hoy = timezone.now().date()
        for pd in productos_data:
            prod, _ = Producto.objects.get_or_create(organization=org, sku=pd['sku'], defaults={
                'nombre': pd['nombre'], 'categoria': pd['categoria'], 
                'precio_base': Decimal(pd['precio']), 'peso_kg': Decimal(pd['peso']), 'unidad': pd['unidad']
            })
            productos.append(prod)
            
            # 6. Crear Lotes (FEFO) para el producto
            if not prod.lotes.exists():
                lote, _ = Lote.objects.get_or_create(
                    producto=prod, codigo_lote=f"LT-{pd['sku']}-26A",
                    defaults={
                        'fecha_caducidad': hoy + timedelta(days=random.randint(60, 360)),
                        'cantidad_inicial': Decimal('500.00'), 'cantidad_disponible': Decimal('500.00')
                    }
                )
                MovimientoInventario.objects.get_or_create(
                    lote=lote, tipo='ENTRADA', cantidad=lote.cantidad_inicial, referencia='Inventario Inicial', created_by=gerente
                )

        # 7. Generar Pedidos y Facturarlos (Se creará Viaje)
        viaje, created_viaje = Viaje.objects.get_or_create(
            organization=org, vehiculo=npr_pesado, fecha=hoy + timedelta(days=1), chofer=chofer1, estado='Programado'
        )

        import random
        from apps.pedidos.services import PedidoService
        from apps.pedidos.utils import generar_numero_pedido
        
        if created_viaje:
            for i, cliente in enumerate(clientes):
                items = []
                # Seleccionar 3 productos al azar
                prods_pedido = random.sample(productos, 3)
                peso_total_pedido = 0

                for p in prods_pedido:
                    cant = random.randint(10, 50)  # Bultos
                    items.append({'producto': p.nombre, 'sku': p.sku, 'cantidad': cant, 'precio': p.precio_base})
                    peso_total_pedido += (cant * float(p.peso_kg))
                
                # Crear directamente el objeto y evitar problemas de session/request
                pedido = Pedido.objects.create(
                    organization=org, numero=generar_numero_pedido(org), created_by=vendedor1,
                    cliente=cliente, vendedor=vendedor1, fecha_pedido=hoy, estado='Confirmado', estado_despacho='Programado'
                )
                
                for item_data in items:
                    PedidoItem.objects.create(pedido=pedido, **item_data)
                
                pedido.recalcular_total()
                
                # Descontar stock
                try:
                    PedidoService.procesar_descuento_stock(pedido, vendedor1)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Stock warning: {e}"))
                
                # Asignar a viaje
                try:
                    vd = ViajeDetalle(viaje=viaje, pedido=pedido, peso_estimado_kg=Decimal(str(peso_total_pedido)))
                    vd.clean() # Valida contra capacidad del camión NPR
                    vd.save()
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"No cabe en el viaje: {e}"))

        self.stdout.write(self.style.SUCCESS('¡Datos de MegaConfites cargados exitosamente!'))
