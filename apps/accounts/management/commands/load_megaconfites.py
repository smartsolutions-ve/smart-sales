import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import Organization, User
from apps.productos.models import CategoriaProducto, Producto, Lote, MovimientoInventario
from apps.pedidos.models import Cliente, Pedido, PedidoItem, Factura, PedidoEstadoHistorial
from apps.flotas.models import Vehiculo, Viaje, ViajeDetalle

class Command(BaseCommand):
    help = 'Carga masiva de datos (histórico 6 meses) para MegaConfites Occidente C.A.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando carga PROFUNDA de datos para MegaConfites...')

        org, _ = Organization.objects.get_or_create(
            name='Distribuidora MegaConfites Occidente, C.A.',
            defaults={'slug': 'megaconfites-occ', 'plan': 'pro'}
        )
        
        # Limpiar datos transaccionales para poder correrlo varias veces sin saturar
        self.stdout.write('Limpiando historial previo...')
        Pedido.objects.filter(organization=org).delete()
        Viaje.objects.filter(organization=org).delete()
        Factura.objects.filter(pedido__organization=org).delete()

        # 1. Usuarios Bases
        gerente, _ = User.objects.get_or_create(username='gerente_mega', defaults={'email': 'gerente@megaconfites.com', 'first_name': 'Carlos', 'last_name': 'Mendoza', 'role': 'gerente', 'organization': org})
        gerente.set_password('Mega2026*')
        gerente.save()

        supervisor, _ = User.objects.get_or_create(username='supervisor_mega', defaults={'email': 'super@megaconfites.com', 'first_name': 'Ana', 'last_name': 'Silva', 'role': 'supervisor', 'organization': org})
        supervisor.set_password('Mega2026*')
        supervisor.save()

        vendedor1, _ = User.objects.get_or_create(username='vendedor_mega1', defaults={'email': 'vendedor1@megaconfites.com', 'first_name': 'Pedro', 'last_name': 'Pérez', 'role': 'vendedor', 'organization': org, 'supervisor_asignado': supervisor})
        vendedor1.set_password('Mega2026*')
        vendedor1.save()
        
        vendedor2, _ = User.objects.get_or_create(username='vendedor_mega2', defaults={'email': 'vendedor2@megaconfites.com', 'first_name': 'Luisa', 'last_name': 'Gomez', 'role': 'vendedor', 'organization': org, 'supervisor_asignado': supervisor})
        vendedor2.set_password('Mega2026*')
        vendedor2.save()

        choferes = []
        for i in range(1, 4):
            c, _ = User.objects.get_or_create(username=f'chofer_mega{i}', defaults={'email': f'chofer{i}@megaconfites.com', 'first_name': f'Chofer {i}', 'role': 'vendedor', 'organization': org})
            c.set_password('Mega2026*')
            c.save()
            choferes.append(c)

        # 2. Vehículos de la Flota
        vehiculos = []
        pesos = [5000, 5000, 8000, 3000, 3000]
        modelos = ['NPR', 'NPR', 'Toronto', 'Cargo 815', 'Cargo 815']
        for i in range(5):
            v, _ = Vehiculo.objects.get_or_create(placa=f'MEGA00{i}', organization=org, defaults={
                'marca': 'Ford/Chevy', 'modelo': modelos[i], 'capacidad_kg': Decimal(pesos[i]), 'chofer_habitual': choferes[i%3]
            })
            vehiculos.append(v)

        # 3. Múltiples Clientes
        nombres_base = ["Euromart", "La Esperanza", "Alemana", "Reina", "M&M", "El Sol", "Dorado", "Central", "San Jose", "Plaza"]
        tipos = ["Supermercado", "Abasto", "Bodegón", "Farmacia", "Agente", "Comercial"]
        clientes = []
        for i in range(30):
            cliente, _ = Cliente.objects.get_or_create(
                organization=org, nombre=f"{random.choice(tipos)} {random.choice(nombres_base)} {i+1}",
                defaults={'contacto': f'Contacto {i}', 'telefono': f'0414-{random.randint(1000000,9999999)}', 'direccion': 'Zona Industrial y Centro'}
            )
            clientes.append(cliente)

        # 4. Catalogos + Productos Varios + Lotes
        cat_viveres, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Víveres Básicos')
        cat_bebidas, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Bebidas y Líquidos')
        cat_higiene, _ = CategoriaProducto.objects.get_or_create(organization=org, nombre='Cuidado Personal')
        
        cats = [cat_viveres, cat_bebidas, cat_higiene]
        productos = []
        hoy = timezone.now().date()
        
        self.stdout.write('Generando 30 Productos con Inventario FEFO...')
        for i in range(30):
            peso = random.choice([5.0, 10.0, 15.0, 20.0, 24.0, 25.0])
            precio = round(random.uniform(10.0, 80.0), 2)
            unidad = random.choice(['Bulto', 'Caja', 'Paca', 'Display'])
            
            prod, _ = Producto.objects.get_or_create(organization=org, sku=f"MEGA-PRD-{i+1}", defaults={
                'nombre': f'Producto Mayorista Bulk {i+1}', 'categoria': random.choice(cats),
                'precio_base': Decimal(str(precio)), 'peso_kg': Decimal(str(peso)), 'unidad': f'{unidad} x {int(peso)}kg'
            })
            productos.append(prod)
            
            # Siempre recuperar al menos 2 lotes
            if prod.lotes.count() < 2:
                for j in range(2):
                    lote, _ = Lote.objects.get_or_create(
                        producto=prod, codigo_lote=f"LT-{prod.sku}-{j}",
                        defaults={'fecha_caducidad': hoy + timedelta(days=random.randint(30, 300)),
                                  'cantidad_inicial': Decimal('5000.00'), 'cantidad_disponible': Decimal('5000.00')}
                    )

        # 5. Carga Histórica Masiva (Pedidos, Viajes, Facturas)
        self.stdout.write('Generando 150 pedidos distribuidos en 6 meses...')
        from apps.pedidos.utils import generar_numero_pedido
        from apps.pedidos.services import PedidoService
        
        estados = ['Entregado', 'Cancelado', 'Entregado', 'Entregado', 'Confirmado', 'Confirmado', 'Pendiente']
        
        viajes = []
        for v in range(30):  # Crear 30 viajes históricos y futuros
            fecha_v = hoy - timedelta(days=random.randint(-10, 150))
            viaje = Viaje.objects.create(
                organization=org, vehiculo=random.choice(vehiculos), fecha=fecha_v, 
                chofer=random.choice(choferes), estado=random.choice(['Completado', 'Completado', 'Programado'])
            )
            viajes.append(viaje)

        vendedores = [vendedor1, vendedor2]
        
        for i in range(150):
            # Distribuir fechas hacia atrás
            dias_atras = random.randint(0, 170)
            fecha_ped = hoy - timedelta(days=dias_atras)
            estado_rnd = random.choice(estados)
            vendedor_act = random.choice(vendedores)
            
            pedido = Pedido.objects.create(
                organization=org, numero=generar_numero_pedido(org), created_by=vendedor_act,
                cliente=random.choice(clientes), vendedor=vendedor_act, fecha_pedido=fecha_ped, 
                estado=estado_rnd, estado_despacho='Despachado' if estado_rnd == 'Entregado' else 'Programado'
            )
            Pedido.objects.filter(pk=pedido.pk).update(created_at=timezone.now() - timedelta(days=dias_atras))
            
            # 2 a 8 items por pedido
            prods = random.sample(productos, random.randint(2, 6))
            peso_pedido = 0
            for p in prods:
                cant = random.randint(5, 50)
                precio_f = float(p.precio_base) * random.uniform(0.9, 1.1)
                PedidoItem.objects.create(pedido=pedido, producto=p.nombre, sku=p.sku, cantidad=cant, precio=round(precio_f, 2))
                peso_pedido += cant * float(p.peso_kg)
            
            pedido.recalcular_total()
            
            # Descontar stock si Confirmado/Entregado
            if pedido.estado in ['Confirmado', 'Entregado']:
                try:
                    PedidoService.procesar_descuento_stock(pedido, vendedor_act)
                    PedidoEstadoHistorial.objects.create(pedido=pedido, estado_anterior='Pendiente', estado_nuevo=pedido.estado, usuario=gerente)
                except:
                    pass
            
            # Asignar a un viaje si no está cancelado, a veces
            if pedido.estado != 'Cancelado' and random.random() > 0.3:
                try:
                    v = random.choice(viajes)
                    vd = ViajeDetalle(viaje=v, pedido=pedido, peso_estimado_kg=Decimal(str(peso_pedido)))
                    vd.clean() # check peso
                    vd.save()
                except:
                    pass # si el camión ya está lleno lo ignora
                    
            # Si fue entregado, generar Factura
            if pedido.estado == 'Entregado' and random.random() > 0.2:
                Factura.objects.create(
                    pedido=pedido, numero_factura=f'F-{pedido.numero[4:]}',
                    fecha_factura=fecha_ped + timedelta(days=random.randint(1, 5)),
                    monto=pedido.total, created_by=gerente
                )
                
        self.stdout.write(self.style.SUCCESS('\n========================================='))
        self.stdout.write(self.style.SUCCESS('¡MEGA DATA INYECTADA CORRECTAMENTE!'))
        self.stdout.write(self.style.SUCCESS(f'• Nro. Pedidos: 150'))
        self.stdout.write(self.style.SUCCESS(f'• Viajes Asignados Controlados por Peso'))
        self.stdout.write(self.style.SUCCESS(f'• Stock Descontado por FEFO'))
        self.stdout.write(self.style.SUCCESS(f'• Facturas Generadas'))
        self.stdout.write(self.style.SUCCESS('========================================='))
