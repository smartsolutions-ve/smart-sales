"""
Crea datos de prueba realistas para El Gran Chaparral 2024 C.A.

Uso:
    python manage.py setup_test_data
    python manage.py setup_test_data --reset   # borra datos previos de la org antes de crear
    python manage.py setup_test_data --password mi_clave
"""
import random
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from apps.accounts.models import Organization, User
from apps.pedidos.models import Cliente, Pedido, PedidoItem
from apps.pedidos.utils import generar_numero_pedido
from apps.competencia.models import CompetenciaRegistro
from apps.productos.models import CategoriaProducto, Producto


# ─── Datos maestros del negocio ──────────────────────────────────────────────

CLIENTES = [
    # (nombre, contacto, telefono, email, direccion)
    ("Granja Los Pinos", "Carlos Medina", "0412-555-1234", "granja.lospinos@gmail.com", "Sector La Morita, Aragua"),
    ("Avícola El Trigal C.A.", "María Quintero", "0414-432-8876", "avicola.trigal@hotmail.com", "Carretera Nacional vía Tinaquillo, Cojedes"),
    ("Finca Santa Bárbara", "José Hernández", "0416-721-4455", "", "Km 12, Vía Acarigua, Portuguesa"),
    ("Agropecuaria Don Pedro", "Pedro Rivas", "0424-810-2200", "donpedro.agro@gmail.com", "Barinas, sector Barinitas"),
    ("Granja Avícola La Esperanza", "Luisa Torrealba", "0412-667-9900", "", "Maracay, Turmero sector industrial"),
    ("Porcícola El Paraíso", "Roberto Solórzano", "0414-111-3344", "porcicola.paraiso@gmail.com", "Guárico, sector Calabozo"),
    ("Distribuidora Agro Llanera", "Ana Sandoval", "0416-990-1122", "agrollanera@gmail.com", "Guanare, Portuguesa"),
    ("Hacienda El Lucero", "Miguel Ángel Pérez", "0424-555-7788", "", "Barinas, vía El Real"),
    ("Explotaciones Bovinas Zulia C.A.", "Carmen Urdaneta", "0412-334-5566", "bovinas.zulia@gmail.com", "Machiques de Perijá, Zulia"),
    ("Granja Cerda Fértil", "Francisco Morales", "0414-876-3310", "", "Valencia, Carabobo zona industrial"),
    ("Inversiones Agrícolas Guárico 2020", "Beatriz Castillo", "0416-440-8899", "agriguarico@hotmail.com", "Valle de La Pascua, Guárico"),
    ("Avicultura del Centro C.A.", "Jorge Contreras", "0424-223-7654", "aviculturacentro@gmail.com", "Cagua, Aragua"),
    ("Rancho El Gavilán", "Simón Ruiz", "0412-998-4411", "", "Apure, Biruaca"),
    ("Agropecuaria Hermanos Bello", "Antonio Bello", "0414-667-0033", "bello.agro@gmail.com", "El Vigía, Mérida"),
    ("Granja Pollos del Sur", "Yolanda Gutiérrez", "0416-555-8822", "", "Barquisimeto, Lara sector industrial"),
    ("Comercial Pecuario El Palmar", "Eduardo Jiménez", "0424-334-5500", "pecuario.palmar@gmail.com", "El Palmar, Bolívar"),
    ("Finca Agromoderna 2024 C.A.", "Liliana Vargas", "0412-121-3344", "agromoderna24@gmail.com", "Calabozo, Guárico"),
    ("Avícola San José del Llano", "Ramón Díaz", "0414-009-2211", "", "Barinas, San Silvestre"),
]

# Productos que El Gran Chaparral VENDE a sus clientes
# (nombre, precio_min_usd, precio_max_usd, categoria)
PRODUCTOS = [
    # ABA — Aves
    ("Pollo Iniciador ALIPA x 40kg", 22, 28, "ABA"),
    ("Pollo Terminador ALIPA x 40kg", 21, 26, "ABA"),
    ("CONAVE P1 Inicio x 40kg", 20, 25, "ABA"),
    ("CONAVE P2 Engorde x 40kg", 20, 25, "ABA"),
    ("Gallinas Ponedoras x 40kg", 22, 27, "ABA"),
    ("Codorniz Postura ENAKA x 30kg", 19, 24, "ABA"),
    # ABA — Cerdos
    ("Cerdo Inicio ALIPA x 40kg", 24, 30, "ABA"),
    ("Cerdo Desarrollo ALIPA x 40kg", 23, 28, "ABA"),
    ("Cerdo Engorde y Terminador x 40kg", 22, 27, "ABA"),
    ("Cerdas Gestantes PUROLOMO x 40kg", 23, 28, "ABA"),
    # ABA — Bovinos
    ("Vaca Lechera 21% x 40kg", 26, 34, "ABA"),
    ("Ganado Carne Engorde x 40kg", 24, 30, "ABA"),
    ("5 Cereales RAGER x 40kg", 20, 25, "ABA"),
    # Subproductos
    ("Afrecho de Maíz x 50kg", 8, 14, "SubProd"),
    ("Maíz Amarillo x 50kg", 10, 16, "SubProd"),
    ("Arroz Pico x 50kg", 9, 15, "SubProd"),
    # Medicinas Veterinarias
    ("Ivermectina Oral 0.25% x 30ml", 3.5, 6, "Medicina"),
    ("Amitraz Calbos x Litro", 8, 14, "Medicina"),
    ("Enrovet x 250ml", 12, 18, "Medicina"),
    ("Ferrovit x 100ml", 4, 7, "Medicina"),
    ("Ferron B12 x 100ml", 5, 8, "Medicina"),
    ("Hermaticina x 100g", 6, 10, "Medicina"),
    ("Coljet x 200ml", 9, 15, "Medicina"),
    ("Convican x 100ml", 7, 12, "Medicina"),
    # Accesorios
    ("Comedero Tubular Pollito x10", 18, 28, "Accesorio"),
    ("Bebedero Campana 3L x5", 15, 22, "Accesorio"),
    # Mascotas
    ("MASCOTA Perrarina x 20kg", 28, 38, "Mascota"),
    ("Alimento Gato Premium x 10kg", 22, 32, "Mascota"),
]

# Competidores que menciona la empresa
COMPETIDORES = [
    "Agro Barinas Distribuidora",
    "Comercial Agrícola del Llano",
    "Agropecuaria Nacional C.A.",
    "Distribuidora Ganadera Llanera",
    "Concentrados del Sur C.A.",
    "AgroCenter Portuguesa",
    "Insumos Agropecuarios El Rayo",
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fecha_aleatoria(dias_atras_min: int, dias_atras_max: int) -> datetime.date:
    dias = random.randint(dias_atras_min, dias_atras_max)
    return timezone.now().date() - datetime.timedelta(days=dias)


def _precio(pmin: float, pmax: float) -> Decimal:
    return Decimal(str(round(random.uniform(pmin, pmax) * 2) / 2))  # múltiplos de 0.50


def _cantidad_aba() -> Decimal:
    """Cantidad de sacos típica para ABA: 20-300 sacos."""
    return Decimal(str(random.choice([20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300])))


def _cantidad_medicina() -> Decimal:
    """Cantidad típica de medicinas: 3-24 unidades."""
    return Decimal(str(random.randint(3, 24)))


def _cantidad_otros() -> Decimal:
    return Decimal(str(random.randint(1, 20)))


def _items_para_pedido(n_items: int = None) -> list[dict]:
    """Genera entre 1 y 5 ítems realistas para un pedido."""
    if n_items is None:
        n_items = random.randint(1, 4)

    items = []
    productos_usados = set()
    for _ in range(n_items):
        prod = random.choice(PRODUCTOS)
        while prod[0] in productos_usados and len(productos_usados) < len(PRODUCTOS):
            prod = random.choice(PRODUCTOS)
        productos_usados.add(prod[0])

        nombre, pmin, pmax, cat = prod
        precio = _precio(pmin, pmax)
        if cat == "ABA":
            cantidad = _cantidad_aba()
        elif cat == "Medicina":
            cantidad = _cantidad_medicina()
        else:
            cantidad = _cantidad_otros()

        items.append({'producto': nombre, 'cantidad': cantidad, 'precio': precio, 'sku': ''})
    return items


ESTADOS_DISTRIBUCION = [
    ('Entregado', 40),
    ('Confirmado', 20),
    ('En Proceso', 15),
    ('Pendiente', 15),
    ('Cancelado', 10),
]

def _estado_aleatorio() -> str:
    estados = [e for e, w in ESTADOS_DISTRIBUCION]
    pesos = [w for e, w in ESTADOS_DISTRIBUCION]
    return random.choices(estados, weights=pesos, k=1)[0]


def _estado_despacho(estado_pedido: str) -> str:
    if estado_pedido == 'Entregado':
        return 'Despachado'
    if estado_pedido == 'Cancelado':
        return 'Pendiente Despacho'
    if estado_pedido == 'Confirmado':
        return random.choice(['Pendiente Despacho', 'Programado'])
    if estado_pedido == 'En Proceso':
        return random.choice(['Programado', 'En Tránsito'])
    return 'Pendiente Despacho'


# ─── Comando principal ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Crea datos de prueba realistas para El Gran Chaparral 2024 C.A.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Elimina pedidos, clientes y competencia de la org antes de crear nuevos datos.'
        )
        parser.add_argument(
            '--password', default='chaparral2024',
            help='Contraseña para los usuarios de prueba (default: chaparral2024)'
        )
        parser.add_argument(
            '--pedidos', type=int, default=45,
            help='Número de pedidos a crear (default: 45)'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']
        n_pedidos = options['pedidos']
        reset = options['reset']

        self.stdout.write('\n🌱 Configurando datos de prueba — El Gran Chaparral 2024 C.A.\n')

        # ── 1. Organización ───────────────────────────────────────────────────
        org, created = Organization.objects.get_or_create(
            slug='gran-chaparral',
            defaults={
                'name': 'El Gran Chaparral 2024 C.A.',
                'plan': 'pro',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Organización creada: {org.name}'))
        else:
            self.stdout.write(f'  → Organización existente: {org.name}')

        # ── 2. Reset opcional ─────────────────────────────────────────────────
        if reset:
            pedidos_del = Pedido.objects.filter(organization=org).count()
            Pedido.objects.filter(organization=org).delete()
            Cliente.objects.filter(organization=org).delete()
            CompetenciaRegistro.objects.filter(organization=org).delete()
            Producto.objects.filter(organization=org).delete()
            CategoriaProducto.objects.filter(organization=org).delete()
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Reset: {pedidos_del} pedidos + clientes + competencia + productos eliminados.'
            ))

        # ── 3. Usuarios ───────────────────────────────────────────────────────
        gerente = self._crear_usuario(
            org=org, username='gerente_chaparral',
            first_name='Carlos', last_name='Medina Suárez',
            email='gerente@granchaparral.com', role='gerente', password=password,
        )
        vendedor1 = self._crear_usuario(
            org=org, username='vendedor_jose',
            first_name='José', last_name='Hernández',
            email='jhernandez@granchaparral.com', role='vendedor', password=password,
        )
        vendedor2 = self._crear_usuario(
            org=org, username='vendedor_maria',
            first_name='María', last_name='Quintero Rojas',
            email='mquintero@granchaparral.com', role='vendedor', password=password,
        )
        vendedores = [gerente, vendedor1, vendedor2]
        self.stdout.write(self.style.SUCCESS(f'  ✓ Usuarios: {len(vendedores)} creados/verificados'))

        # ── 4. Clientes ───────────────────────────────────────────────────────
        clientes_db = []
        for nombre, contacto, telefono, email, direccion in CLIENTES:
            cliente, _ = Cliente.objects.get_or_create(
                organization=org,
                nombre=nombre,
                defaults={
                    'contacto': contacto,
                    'telefono': telefono,
                    'email': email,
                    'direccion': direccion,
                },
            )
            clientes_db.append(cliente)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Clientes: {len(clientes_db)} creados/verificados'))

        # ── 5. Catálogo de Productos ─────────────────────────────────────────
        CATEGORIAS_MAP = {
            'ABA': 'Alimentos Balanceados (ABA)',
            'SubProd': 'Subproductos y Materias Primas',
            'Medicina': 'Medicinas Veterinarias',
            'Accesorio': 'Accesorios y Equipos',
            'Mascota': 'Productos para Mascotas',
        }
        categorias_db = {}
        for clave, nombre_cat in CATEGORIAS_MAP.items():
            cat, _ = CategoriaProducto.objects.get_or_create(
                organization=org, nombre=nombre_cat,
            )
            categorias_db[clave] = cat

        SKU_PREFIJOS = {
            'ABA': 'ABA', 'SubProd': 'SUB', 'Medicina': 'MED',
            'Accesorio': 'ACC', 'Mascota': 'MAS',
        }
        productos_creados = 0
        for i, (nombre, pmin, pmax, cat_clave) in enumerate(PRODUCTOS, start=1):
            precio_promedio = Decimal(str(round((pmin + pmax) / 2, 2)))
            unidad = 'saco' if cat_clave in ('ABA', 'SubProd') else 'unidad'
            sku = f'{SKU_PREFIJOS[cat_clave]}-{i:03d}'
            _, created = Producto.objects.get_or_create(
                organization=org, nombre=nombre,
                defaults={
                    'sku': sku,
                    'precio_base': precio_promedio,
                    'categoria': categorias_db[cat_clave],
                    'unidad': unidad,
                    'is_active': True,
                },
            )
            if created:
                productos_creados += 1

        total_productos = Producto.objects.filter(organization=org).count()
        if productos_creados > 0:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Productos: {productos_creados} creados ({total_productos} total)'))
        else:
            self.stdout.write(f'  → Productos: ya existen {total_productos} (sin crear nuevos)')

        # ── 6. Pedidos ────────────────────────────────────────────────────────
        pedidos_existentes = Pedido.objects.filter(organization=org).count()
        pedidos_a_crear = n_pedidos - pedidos_existentes
        pedidos_creados = 0

        if pedidos_a_crear <= 0:
            self.stdout.write(f'  → Pedidos: ya existen {pedidos_existentes} (sin crear nuevos)')
        else:
            for _ in range(pedidos_a_crear):
                estado = _estado_aleatorio()
                dias_min = 5 if estado == 'Entregado' else 0
                fecha_pedido = _fecha_aleatoria(dias_min, 90)
                fecha_entrega = None
                if estado not in ('Cancelado',):
                    fecha_entrega = fecha_pedido + datetime.timedelta(
                        days=random.randint(2, 10)
                    )

                vendedor = random.choice(vendedores)
                cliente = random.choice(clientes_db)
                items = _items_para_pedido()

                pedido = Pedido.objects.create(
                    organization=org,
                    numero=generar_numero_pedido(org),
                    fecha_pedido=fecha_pedido,
                    fecha_entrega=fecha_entrega,
                    cliente=cliente,
                    vendedor=vendedor,
                    created_by=vendedor,
                    estado=estado,
                    estado_despacho=_estado_despacho(estado),
                    observaciones=random.choice([
                        '', '', '',
                        'Cliente solicita entrega temprana.',
                        'Pago acordado contra entrega.',
                        'Requiere factura a nombre de la granja.',
                        'Confirmar disponibilidad antes de despachar.',
                        'Cliente habitual — crédito 15 días.',
                    ]),
                )
                for item_data in items:
                    PedidoItem.objects.create(pedido=pedido, **item_data)
                pedido.recalcular_total()
                pedidos_creados += 1

            self.stdout.write(self.style.SUCCESS(
                f'  ✓ Pedidos: {pedidos_creados} creados ({Pedido.objects.filter(organization=org).count()} total)'
            ))

        # ── 7. Registros de competencia ───────────────────────────────────────
        comp_existentes = CompetenciaRegistro.objects.filter(organization=org).count()
        comp_data = [
            ("Pollo Iniciador ALIPA x 40kg", "Agro Barinas Distribuidora", 21.00, 24.50,
             "Ofrecen precio ligeramente menor. Ajustamos precio para cliente Granja Los Pinos."),
            ("Cerdo Inicio ALIPA x 40kg", "Concentrados del Sur C.A.", 22.00, 25.00,
             "Competidor entrega en finca. Propusimos descuento por volumen."),
            ("Vaca Lechera 21% x 40kg", "Comercial Agrícola del Llano", 24.00, 27.00,
             "Nuestra calidad es superior. Cliente eligió nuestra oferta."),
            ("MASCOTA Perrarina x 20kg", "AgroCenter Portuguesa", 26.00, 30.00,
             "Precio competidor más bajo. Estamos evaluando ajuste de precio."),
            ("Afrecho de Maíz x 50kg", "Distribuidora Ganadera Llanera", 10.00, 12.50,
             "Producto similar. Competidor ofrece transporte incluido."),
            ("Ivermectina Oral 0.25% x 30ml", "Insumos Agropecuarios El Rayo", 4.00, 5.00,
             "Misma marca. Ofrecemos mejor servicio post-venta."),
            ("Pollo Terminador ALIPA x 40kg", "Agropecuaria Nacional C.A.", 20.00, 23.00,
             "Competidor nuevo en la zona. Monitorear su oferta."),
            ("Gallinas Ponedoras x 40kg", "AgroCenter Portuguesa", 20.50, 23.50,
             "Cliente Avícola El Trigal comparó precios. Mantuvimos relación por volumen."),
            ("Comedero Tubular Pollito x10", "Distribuidora Ganadera Llanera", 15.00, 20.00,
             "Accesorios más económicos en competidor. Consideramos incluir garantía."),
            ("Cerdo Engorde y Terminador x 40kg", "Concentrados del Sur C.A.", 20.00, 24.00,
             "Sin diferencia significativa de precio. Cliente prefiere nuestro crédito."),
        ]

        comp_creados = 0
        for i, (producto, competidor, precio_comp, precio_nuestro, accion) in enumerate(comp_data):
            if comp_existentes > 0:
                break
            cliente_comp = random.choice(clientes_db) if random.random() > 0.3 else None
            vendedor_comp = random.choice(vendedores)
            CompetenciaRegistro.objects.create(
                organization=org,
                fecha=_fecha_aleatoria(3, 75),
                vendedor=vendedor_comp,
                cliente=cliente_comp,
                producto=producto,
                competidor=competidor,
                precio_comp=Decimal(str(precio_comp)),
                precio_nuestro=Decimal(str(precio_nuestro)),
                accion_tomada=accion,
            )
            comp_creados += 1

        if comp_existentes > 0:
            self.stdout.write(f'  → Competencia: ya existen {comp_existentes} registros (sin crear nuevos)')
        else:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Competencia: {comp_creados} registros creados'))

        # ── 8. Resumen ────────────────────────────────────────────────────────
        total_pedidos = Pedido.objects.filter(organization=org).count()
        total_clientes = Cliente.objects.filter(organization=org).count()
        total_productos = Producto.objects.filter(organization=org).count()
        total_comp = CompetenciaRegistro.objects.filter(organization=org).count()

        self.stdout.write('\n' + '─' * 55)
        self.stdout.write(self.style.SUCCESS('  ✓ Setup completado exitosamente\n'))
        self.stdout.write(f'  Organización : {org.name}')
        self.stdout.write(f'  Clientes     : {total_clientes}')
        self.stdout.write(f'  Productos    : {total_productos}')
        self.stdout.write(f'  Pedidos      : {total_pedidos}')
        self.stdout.write(f'  Competencia  : {total_comp} registros')
        self.stdout.write(f'\n  Credenciales de acceso:')
        self.stdout.write(f'  ┌─ Gerente   → usuario: gerente_chaparral | clave: {password}')
        self.stdout.write(f'  ├─ Vendedor  → usuario: vendedor_jose     | clave: {password}')
        self.stdout.write(f'  └─ Vendedor  → usuario: vendedor_maria    | clave: {password}')
        self.stdout.write(f'\n  Accede en: http://127.0.0.1:8000/login/')
        self.stdout.write('─' * 55 + '\n')

    def _crear_usuario(self, org, username, first_name, last_name, email, role, password):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'organization': org,
                'role': role,
                'is_active': True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user
