"""
Crea datos de prueba para FAPARCA (Fábrica de Pastas y Harinas).

FAPARCA es un complejo industrial en Guanare, Portuguesa, Venezuela.
Produce pastas alimenticias (largas y cortas), harinas (panaderas,
pasteleras, galleteras, sémola) y una línea libre de gluten (marca Gisela).
Fundada en 1957 como "Pastas Rosana" por inmigrantes italianos.

Uso:
    python manage.py setup_faparca_data
    python manage.py setup_faparca_data --reset
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Organization, User
from apps.pedidos.models import Cliente, Pedido, PedidoItem, Factura
from apps.productos.models import CategoriaProducto, Producto
from apps.competencia.models import CompetenciaRegistro
from apps.flotas.models import Vehiculo, Viaje, ViajeDetalle
from apps.cuotas.models import Zona, TasaCambio, VentaMensual


# ── Datos maestros ───────────────────────────────────────────────

VENDEDORES = [
    ('jperez', 'Juan', 'Pérez', 'gerente'),
    ('mrodriguez', 'María', 'Rodríguez', 'vendedor'),
    ('lgomez', 'Luis', 'Gómez', 'vendedor'),
    ('asilva', 'Ana', 'Silva', 'vendedor'),
]

CLIENTES_DATA = [
    # Distribuidores, panaderías, supermercados, mayoristas típicos de FAPARCA
    ("Distribuidora La Portuguesa C.A.", "Carlos Mendoza", "0412-555-0101", "Guanare, Portuguesa"),
    ("Supermercados El Llano S.A.", "Rosa Hernández", "0414-555-0202", "Acarigua, Portuguesa"),
    ("Panadería y Pastelería Don Trigo", "Marco Rinaldi", "0416-555-0303", "Barquisimeto, Lara"),
    ("Mayorista Central de Harinas", "Jorge Ramírez", "0424-555-0404", "Valencia, Carabobo"),
    ("Distribuidora Alimentos del Centro", "Patricia Campos", "0412-555-0505", "Maracay, Aragua"),
    ("Automercados La Familia", "Andrés Moreno", "0414-555-0606", "Barinas, Barinas"),
    ("Panadería Artesanal El Molino", "Giuseppe Conti", "0416-555-0707", "San Cristóbal, Táchira"),
    ("Comercializadora Gran Llano C.A.", "Sofía Herrera", "0424-555-0808", "San Carlos, Cojedes"),
    ("Cadena de Panaderías La Espiga", "Fernando Torres", "0412-555-0909", "Barquisimeto, Lara"),
    ("Distribuciones Alimentarias del Sur", "Carmen López", "0414-555-1010", "San Fernando, Apure"),
    ("Supermercado Don Pancho", "Manuel Briceño", "0416-555-1111", "Araure, Portuguesa"),
    ("Mayorista Harinas y Pastas Zulia", "Raúl Flores", "0424-555-1212", "Maracaibo, Zulia"),
    ("Pizzería y Restaurante Bella Italia", "Antonio Ferretti", "0412-555-1313", "Caracas, Dtto. Capital"),
    ("Red de Abastos Comunales Portuguesa", "Diana Castillo", "0414-555-1414", "Turén, Portuguesa"),
    ("Inversiones Alimenticias Miranda C.A.", "Javier Paredes", "0416-555-1515", "Los Teques, Miranda"),
]

CATEGORIAS = [
    'Pastas Largas',
    'Pastas Cortas',
    'Harinas',
    'Sémolas',
    'Línea Gluten Free (Gisela)',
]

PRODUCTOS_DATA = [
    # (nombre, sku, categoria_idx, precio_base, unidad, peso_kg)
    # ── Pastas Largas ──
    ("Espagueti Rosana 1kg", "PL-001", 0, 2.80, "paquete 1kg", 1),
    ("Espagueti Rosana 500g", "PL-002", 0, 1.50, "paquete 500g", 0.5),
    ("Vermicelli Rosana 1kg", "PL-003", 0, 2.80, "paquete 1kg", 1),
    ("Linguini Rosana 500g", "PL-004", 0, 1.60, "paquete 500g", 0.5),
    ("Fettuccine Rosana 500g", "PL-005", 0, 1.70, "paquete 500g", 0.5),
    # ── Pastas Cortas ──
    ("Tornillo Rosana 500g", "PC-001", 1, 1.50, "paquete 500g", 0.5),
    ("Pluma Rosana 500g", "PC-002", 1, 1.50, "paquete 500g", 0.5),
    ("Codito Rosana 500g", "PC-003", 1, 1.45, "paquete 500g", 0.5),
    ("Macarrón Rosana 1kg", "PC-004", 1, 2.70, "paquete 1kg", 1),
    ("Caracol Rosana 500g", "PC-005", 1, 1.55, "paquete 500g", 0.5),
    # ── Harinas ──
    ("Harina Panadera Faparca 45kg", "HA-001", 2, 28.00, "saco 45kg", 45),
    ("Harina Panadera Faparca 10kg", "HA-002", 2, 7.50, "saco 10kg", 10),
    ("Harina Pastelera Faparca 45kg", "HA-003", 2, 30.00, "saco 45kg", 45),
    ("Harina Galletera Faparca 45kg", "HA-004", 2, 29.00, "saco 45kg", 45),
    ("Harina Todo Uso Faparca 1kg", "HA-005", 2, 1.20, "paquete 1kg", 1),
    # ── Sémolas ──
    ("Sémola de Trigo Duro Faparca 45kg", "SE-001", 3, 32.00, "saco 45kg", 45),
    ("Sémola de Trigo Duro Faparca 10kg", "SE-002", 3, 8.50, "saco 10kg", 10),
    # ── Línea Gluten Free (Gisela) ──
    ("Espagueti Gisela Sin Gluten 500g", "GF-001", 4, 3.50, "paquete 500g", 0.5),
    ("Codito Gisela Sin Gluten 500g", "GF-002", 4, 3.50, "paquete 500g", 0.5),
    ("Tornillo Gisela Sin Gluten 500g", "GF-003", 4, 3.60, "paquete 500g", 0.5),
]

COMPETIDORES = [
    "Pastas Capri (Cargill)",
    "Pastas Sindoni",
    "Pastas Primor (Polar)",
    "Molinos Nacionales (Monaca)",
    "Pastas Valencia",
]

VEHICULOS_DATA = [
    ("ABC-123", "Ford", "Cargo 1722", 12000),
    ("DEF-456", "Chevrolet", "NPR 816", 5000),
    ("GHI-789", "Iveco", "Tector 170E22", 10000),
    ("JKL-012", "Toyota", "Dyna 300", 3000),
    ("MNO-345", "Ford", "F-600", 7000),
]

ZONAS = [
    ("Portuguesa", "POR"),
    ("Lara", "LAR"),
    ("Carabobo", "CAR"),
    ("Barinas", "BAR"),
    ("Aragua", "ARA"),
    ("Táchira", "TAC"),
    ("Zulia", "ZUL"),
    ("Caracas / Miranda", "CCS"),
    ("Cojedes", "COJ"),
    ("Apure", "APU"),
]


class Command(BaseCommand):
    help = 'Crea datos de prueba para FAPARCA (Fábrica de Pastas, Harinas y Gluten Free)'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Borrar datos previos de Faparca')
        parser.add_argument('--password', default='faparca2026',
                            help='Contraseña para los usuarios de prueba')

    @transaction.atomic
    def handle(self, *args, **options):
        org, _ = Organization.objects.get_or_create(
            slug='faparca',
            defaults={
                'name': 'FAPARCA — Fábrica de Pastas Rosana C.A.',
                'is_active': True,
                'plan': 'pro',
            },
        )
        # Actualizar nombre si ya existía con nombre viejo
        if org.name == 'Faparca':
            org.name = 'FAPARCA — Fábrica de Pastas Rosana C.A.'
            org.save(update_fields=['name'])

        if options['reset']:
            self.stdout.write('Borrando datos previos de FAPARCA...')
            VentaMensual.objects.filter(organization=org).delete()
            TasaCambio.objects.filter(organization=org).delete()
            Zona.objects.filter(organization=org).delete()
            ViajeDetalle.objects.filter(viaje__organization=org).delete()
            Viaje.objects.filter(organization=org).delete()
            Vehiculo.objects.filter(organization=org).delete()
            CompetenciaRegistro.objects.filter(organization=org).delete()
            Factura.objects.filter(pedido__organization=org).delete()
            PedidoItem.objects.filter(pedido__organization=org).delete()
            Pedido.objects.filter(organization=org).delete()
            Cliente.objects.filter(organization=org).delete()
            Producto.objects.filter(organization=org).delete()
            CategoriaProducto.objects.filter(organization=org).delete()
            User.objects.filter(organization=org).exclude(
                username='sabh').delete()

        password = options['password']

        # ── Usuarios ──
        users = {}
        for username, first, last, role in VENDEDORES:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first, 'last_name': last,
                    'role': role, 'organization': org,
                    'is_active': True,
                },
            )
            if created:
                u.set_password(password)
                u.save()
            users[username] = u
        gerente = users['jperez']

        # Asegurar que el usuario existente de Faparca sea gerente
        User.objects.filter(organization=org).exclude(
            pk__in=[u.pk for u in users.values()]
        ).update(role='gerente')

        self.stdout.write(f'  Usuarios: {len(users)}')

        # ── Categorías y Productos ──
        cats = {}
        for cat_name in CATEGORIAS:
            c, _ = CategoriaProducto.objects.get_or_create(
                organization=org, nombre=cat_name)
            cats[cat_name] = c

        productos = []
        for nombre, sku, cat_idx, precio, unidad, peso in PRODUCTOS_DATA:
            p, _ = Producto.objects.get_or_create(
                organization=org, sku=sku,
                defaults={
                    'nombre': nombre,
                    'categoria': cats[CATEGORIAS[cat_idx]],
                    'precio_base': Decimal(str(precio)),
                    'unidad': unidad,
                    'peso_kg': Decimal(str(peso)),
                    'is_active': True,
                },
            )
            productos.append(p)

        self.stdout.write(f'  Productos: {len(productos)}')

        # ── Clientes ──
        clientes = []
        for nombre, contacto, tel, dir in CLIENTES_DATA:
            c, _ = Cliente.objects.get_or_create(
                organization=org, nombre=nombre,
                defaults={
                    'contacto': contacto, 'telefono': tel,
                    'direccion': dir,
                },
            )
            clientes.append(c)

        self.stdout.write(f'  Clientes: {len(clientes)}')

        # ── Pedidos (últimos 3 meses) ──
        hoy = date.today()
        vendedores = [users['mrodriguez'], users['lgomez'], users['asilva']]
        estados = ['Pendiente', 'Confirmado', 'En Proceso', 'Entregado', 'Entregado',
                    'Entregado', 'Cancelado']
        estados_desp = {
            'Pendiente': 'Pendiente Despacho',
            'Confirmado': 'Programado',
            'En Proceso': 'En Tránsito',
            'Entregado': 'Despachado',
            'Cancelado': 'Pendiente Despacho',
        }

        pedidos = []
        num = 1
        for days_ago in range(90, 0, -1):
            # 0-4 pedidos por día (FAPARCA tiene buen volumen)
            n_pedidos = random.choices([0, 1, 2, 2, 3, 4], weights=[1, 2, 3, 3, 3, 2])[0]
            for _ in range(n_pedidos):
                fecha = hoy - timedelta(days=days_ago)
                estado = random.choice(estados)
                if days_ago < 5:
                    estado = random.choice(['Pendiente', 'Confirmado', 'En Proceso'])

                cliente = random.choice(clientes)
                vendedor = random.choice(vendedores)
                numero = f'FAP-{num:04d}'
                num += 1

                # Observaciones realistas
                observaciones = random.choice([
                    '',
                    '',
                    'Entregar en horario de mañana',
                    'Cliente solicita factura fiscal',
                    'Incluir muestra de línea Gisela',
                    'Urgente — panadería sin stock',
                    'Pedido recurrente mensual',
                    'Despachar junto con pedido anterior',
                    'Cliente nuevo, primera compra',
                    'Coordinar entrega con transportista externo',
                ])

                p = Pedido.objects.create(
                    organization=org,
                    numero=numero,
                    fecha_pedido=fecha,
                    fecha_entrega=fecha + timedelta(days=random.randint(2, 7)),
                    cliente=cliente,
                    vendedor=vendedor,
                    estado=estado,
                    estado_despacho=estados_desp.get(estado, 'Pendiente Despacho'),
                    observaciones=observaciones,
                    created_by=vendedor,
                    total=0,
                )

                # 1-6 items por pedido
                total = Decimal('0')
                n_items = random.randint(1, 6)
                used = set()

                # Panaderías compran más harinas, supermercados más pastas
                if 'Panadería' in cliente.nombre or 'Panader' in cliente.nombre:
                    pool = [p for p in productos if p.sku.startswith(('HA-', 'SE-'))] + productos
                elif 'Supermercado' in cliente.nombre or 'Automercado' in cliente.nombre:
                    pool = [p for p in productos if p.sku.startswith(('PL-', 'PC-', 'GF-'))] + productos
                else:
                    pool = productos

                for _ in range(n_items):
                    prod = random.choice(pool)
                    if prod.pk in used:
                        continue
                    used.add(prod.pk)

                    # Cantidades realistas según tipo de producto
                    if prod.sku.startswith('HA-') and '45kg' in prod.unidad:
                        cant = Decimal(str(random.choice([10, 20, 30, 50, 100, 200])))
                    elif prod.sku.startswith('SE-') and '45kg' in prod.unidad:
                        cant = Decimal(str(random.choice([10, 20, 50, 100])))
                    elif prod.sku.startswith('GF-'):
                        cant = Decimal(str(random.choice([24, 48, 72, 96, 144])))
                    else:
                        cant = Decimal(str(random.choice([24, 48, 96, 144, 240, 480])))

                    precio = prod.precio_base * Decimal(str(random.uniform(0.92, 1.08)))
                    precio = precio.quantize(Decimal('0.01'))
                    PedidoItem.objects.create(
                        pedido=p, producto=prod.nombre, sku=prod.sku,
                        cantidad=cant, precio=precio,
                    )
                    total += cant * precio

                p.total = total.quantize(Decimal('0.01'))
                p.save(update_fields=['total'])
                pedidos.append(p)

        self.stdout.write(f'  Pedidos: {len(pedidos)}')

        # ── Facturas (para pedidos entregados y algunos en proceso) ──
        n_facturas = 0
        for p in pedidos:
            if p.estado in ('Entregado', 'En Proceso') and random.random() < 0.7:
                monto = p.total if random.random() < 0.8 else (
                    p.total * Decimal('0.5')).quantize(Decimal('0.01'))
                Factura.objects.create(
                    pedido=p,
                    numero_factura=f'F-{random.randint(10000, 99999)}',
                    fecha_factura=p.fecha_pedido + timedelta(
                        days=random.randint(1, 5)),
                    monto=monto,
                    created_by=gerente,
                )
                n_facturas += 1

        self.stdout.write(f'  Facturas: {n_facturas}')

        # ── Competencia ──
        n_comp = 0
        acciones_comp = [
            'Se ofreció descuento por volumen del 5%',
            'Se mantuvo precio; el cliente valora la tradición Rosana',
            'Se ajustó precio para igualar competidor',
            'Se ofreció plan de crédito a 30 días',
            'Se incluyó muestra gratis de línea Gisela',
            'Se propuso combo pastas + harinas con descuento',
            'Cliente prefiere nuestra calidad de sémola de trigo duro',
            '',
        ]
        for _ in range(25):
            prod = random.choice(productos)
            nuestro = float(prod.precio_base or 2)
            comp_precio = nuestro * random.uniform(0.80, 1.25)
            CompetenciaRegistro.objects.create(
                organization=org,
                fecha=hoy - timedelta(days=random.randint(1, 60)),
                cliente=random.choice(clientes),
                vendedor=random.choice(vendedores),
                producto=prod.nombre,
                competidor=random.choice(COMPETIDORES),
                precio_comp=Decimal(str(round(comp_precio, 2))),
                precio_nuestro=prod.precio_base,
                accion_tomada=random.choice(acciones_comp),
            )
            n_comp += 1

        self.stdout.write(f'  Competencia: {n_comp}')

        # ── Vehículos y Viajes ──
        vehiculos = []
        for placa, marca, modelo, cap in VEHICULOS_DATA:
            v, _ = Vehiculo.objects.get_or_create(
                organization=org, placa=placa,
                defaults={
                    'marca': marca, 'modelo': modelo,
                    'capacidad_kg': Decimal(str(cap)),
                    'chofer_habitual': random.choice(vendedores),
                    'is_active': True,
                },
            )
            vehiculos.append(v)

        self.stdout.write(f'  Vehículos: {len(vehiculos)}')

        # Viajes para pedidos despachados
        pedidos_despachados = [p for p in pedidos
                               if p.estado_despacho == 'Despachado']
        n_viajes = 0
        batch = []
        for p in pedidos_despachados:
            batch.append(p)
            if len(batch) >= random.randint(2, 5):
                vehiculo = random.choice(vehiculos)
                viaje = Viaje.objects.create(
                    organization=org,
                    vehiculo=vehiculo,
                    chofer=vehiculo.chofer_habitual or random.choice(vendedores),
                    fecha=batch[0].fecha_pedido + timedelta(
                        days=random.randint(1, 4)),
                    estado='Completado',
                    km_recorridos=Decimal(str(random.randint(40, 350))),
                    costo_flete=Decimal(str(random.randint(25, 180))),
                    created_by=gerente,
                )
                for i, ped in enumerate(batch):
                    peso = sum(
                        float(item.cantidad) * float(
                            next((pr.peso_kg for pr in productos
                                  if pr.sku == item.sku), 1)
                        )
                        for item in ped.items.all()
                    )
                    ViajeDetalle.objects.create(
                        viaje=viaje, pedido=ped,
                        peso_estimado_kg=Decimal(str(round(peso, 2))),
                        orden_entrega=i + 1,
                    )
                n_viajes += 1
                batch = []

        # Viajes programados (próximos días)
        pedidos_pendientes = [p for p in pedidos
                              if p.estado_despacho in (
                                  'Pendiente Despacho', 'Programado')][:8]
        if pedidos_pendientes:
            for chunk_start in range(0, len(pedidos_pendientes), 3):
                chunk = pedidos_pendientes[chunk_start:chunk_start + 3]
                vehiculo = random.choice(vehiculos)
                viaje = Viaje.objects.create(
                    organization=org,
                    vehiculo=vehiculo,
                    chofer=vehiculo.chofer_habitual or vendedores[0],
                    fecha=hoy + timedelta(days=random.randint(1, 3)),
                    estado='Programado',
                    created_by=gerente,
                )
                for i, ped in enumerate(chunk):
                    ViajeDetalle.objects.create(
                        viaje=viaje, pedido=ped,
                        peso_estimado_kg=Decimal(
                            str(random.randint(200, 2000))),
                        orden_entrega=i + 1,
                    )
                n_viajes += 1

        self.stdout.write(f'  Viajes: {n_viajes}')

        # ── Zonas y Cuotas ──
        zonas = {}
        for nombre, codigo in ZONAS:
            z, _ = Zona.objects.get_or_create(
                organization=org, nombre=nombre,
                defaults={'codigo': codigo},
            )
            zonas[nombre] = z

        # Tasas de cambio últimos 3 meses (Bs por USD — BCV)
        tasa_base = 86.0  # Tasa BCV aprox marzo 2026
        for days_ago in [0, 3, 7, 14, 21, 30, 45, 60, 75, 90]:
            # La tasa sube gradualmente
            variacion = (90 - days_ago) * 0.05
            tasa_val = Decimal(str(round(
                tasa_base + variacion + random.uniform(-0.5, 0.5), 4)))
            TasaCambio.objects.get_or_create(
                organization=org,
                fecha=hoy - timedelta(days=days_ago),
                fuente='BCV',
                defaults={'tasa_bs_por_usd': tasa_val},
            )

        self.stdout.write(f'  Tasas de cambio: 10')

        # VentaMensual para últimos 6 meses (más datos)
        n_ventas = 0
        vend_nombres = ['María Rodríguez', 'Luis Gómez', 'Ana Silva']
        zona_nombres = list(zonas.keys())

        for months_ago in range(6):
            periodo = (hoy.replace(day=1) - timedelta(
                days=30 * months_ago)).replace(day=1)
            for prod in productos:
                for vend_name in vend_nombres:
                    zona_name = random.choice(zona_nombres)
                    zona = zonas[zona_name]

                    # Cantidades plan realistas por tipo de producto
                    if prod.sku.startswith('HA-') and '45kg' in prod.unidad:
                        plan_cant = Decimal(str(random.randint(200, 800)))
                    elif prod.sku.startswith('SE-'):
                        plan_cant = Decimal(str(random.randint(100, 400)))
                    elif prod.sku.startswith('GF-'):
                        plan_cant = Decimal(str(random.randint(100, 500)))
                    else:
                        plan_cant = Decimal(str(random.randint(500, 3000)))

                    plan_precio = prod.precio_base or Decimal('2')
                    plan_venta = plan_cant * plan_precio
                    plan_costo = (plan_venta * Decimal('0.62')).quantize(
                        Decimal('0.01'))
                    plan_margen = (plan_venta - plan_costo).quantize(
                        Decimal('0.01'))

                    # Cumplimiento varía: meses recientes mejor
                    base_cumpl = 0.7 + (6 - months_ago) * 0.05
                    cumpl = Decimal(str(random.uniform(
                        base_cumpl - 0.15, base_cumpl + 0.2)))
                    real_cant = (plan_cant * cumpl).quantize(Decimal('1'))
                    real_venta = (plan_venta * cumpl).quantize(
                        Decimal('0.01'))
                    real_costo = (real_venta * Decimal('0.60')).quantize(
                        Decimal('0.01'))

                    # Bolívares (tasa aprox)
                    tasa_mes = Decimal(str(
                        tasa_base - months_ago * 1.5))
                    real_venta_ves = (real_venta * tasa_mes).quantize(
                        Decimal('0.01'))

                    canal = random.choice(['DIRECTO', 'DISTRIBUCIÓN'])

                    VentaMensual.objects.get_or_create(
                        organization=org,
                        periodo=periodo,
                        vendedor_nombre=vend_name,
                        producto_nombre=prod.nombre,
                        zona_nombre=zona_name,
                        defaults={
                            'codigo_producto': prod.sku,
                            'canal': canal,
                            'distribucion': 'Propia' if canal == 'DIRECTO' else random.choice(
                                ['Dist. La Portuguesa', 'Dist. Central',
                                 'Dist. del Sur']),
                            'zona': zona,
                            'plan_cantidad': plan_cant,
                            'plan_precio_usd': plan_precio,
                            'plan_venta_usd': plan_venta,
                            'plan_costo_usd': plan_costo,
                            'plan_margen_usd': plan_margen,
                            'real_cantidad': real_cant,
                            'real_venta_usd': real_venta,
                            'real_venta_ves': real_venta_ves,
                            'real_costo_usd': real_costo,
                        },
                    )
                    n_ventas += 1

        self.stdout.write(f'  Cuotas/Ventas: {n_ventas}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Datos de FAPARCA creados exitosamente.\n'
            f'  Org: {org.name}\n'
            f'  Login: jperez / {password} (gerente)\n'
            f'         mrodriguez / {password} (vendedor)\n'
            f'         lgomez / {password} (vendedor)\n'
            f'         asilva / {password} (vendedor)'
        ))
