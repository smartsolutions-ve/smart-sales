"""
Genera una organización de prueba con historia larga (24 meses por defecto)
para ver las gráficas y reportes de SmartSales con datos de largo plazo.

Crea una organización propia ("Distribuidora Los Llanos Demo C.A.", slug
`demo-historico`) para no chocar con los seeds de build.sh (setup_test_data
--reset borra Gran Chaparral en cada deploy).

Qué genera, todo coherente entre sí:
- Usuarios: gerente, administración (facturador), 2 supervisores (líderes de
  zona) con sus vendedores, choferes y el superadmin de la plataforma.
- Catálogo (categorías, productos, lotes y movimientos), clientes con crédito.
- Pedidos con tendencia de crecimiento + estacionalidad (pico en diciembre),
  facturas, pagos (CxC con algunos clientes morosos), viajes de flota,
  cotizaciones, visitas, devoluciones, registros de competencia, tasas BCV
  y cuotas mensuales (plan vs real).

Contraseñas: si existe la variable de entorno SEED_CREDENCIALES (JSON
{"usuario": "clave"}), se toman de ahí y NO se imprimen (útil en Render, donde
los logs de build quedan guardados). Si un usuario no está en esa variable, se
genera una clave al azar y se imprime UNA sola vez. Nunca se guardan en el
repositorio. Si el usuario ya existe, no se toca su contraseña (salvo con
--reset-passwords).

Uso:
    python manage.py seed_historico
    python manage.py seed_historico --reset           # borra la org demo y la recrea
    python manage.py seed_historico --meses 36
    python manage.py seed_historico --reset-passwords # regenera claves de los usuarios demo
"""
import datetime
import json
import os
import random
import secrets
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.competencia.models import CompetenciaRegistro
from apps.configuracion.models import MetodoPago, ZonaDespacho
from apps.configuracion.models import TasaCambio as TasaConfig
from apps.cotizaciones.models import Cotizacion, CotizacionItem
from apps.cuotas.models import TasaCambio as TasaCuotas
from apps.cuotas.models import VentaMensual, Zona
from apps.cxc.models import Pago
from apps.devoluciones.models import Devolucion, DevolucionItem
from apps.flotas.models import Vehiculo, Viaje, ViajeDetalle
from apps.pedidos.models import Cliente, Factura, Pedido, PedidoItem
from apps.pedidos.utils import generar_numero_pedido
from apps.productos.models import CategoriaProducto, Lote, MovimientoInventario, Producto
from apps.visitas.models import VisitaComercial

ORG_SLUG = 'demo-historico'
ORG_NOMBRE = 'Distribuidora Los Llanos Demo C.A.'
CENT = Decimal('0.01')

# (username, nombre, apellido, rol, zona o None)
USUARIOS = [
    ('gerente.llanos',     'Andrés',   'Colmenares', 'gerente',    None),
    ('admin.llanos',       'Daniela',  'Rengifo',    'facturador', None),
    ('supervisor.norte',   'Rafael',   'Montilla',   'supervisor', 'Norte'),
    ('supervisor.sur',     'Gabriela', 'Pacheco',    'supervisor', 'Sur'),
    ('vendedor.luis',      'Luis',     'Araujo',     'vendedor',   'Norte'),
    ('vendedor.karla',     'Karla',    'Villegas',   'vendedor',   'Norte'),
    ('vendedor.jesus',     'Jesús',    'Oropeza',    'vendedor',   'Norte'),
    ('vendedor.marielys',  'Marielys', 'Pérez',      'vendedor',   'Sur'),
    ('vendedor.orlando',   'Orlando',  'Chirinos',   'vendedor',   'Sur'),
    ('vendedor.yusmary',   'Yusmary',  'Linares',    'vendedor',   'Sur'),
    ('chofer.ramon',       'Ramón',    'Escalona',   'facturador', None),
    ('chofer.wilmer',      'Wilmer',   'Duarte',     'facturador', None),
    ('chofer.eduardo',     'Eduardo',  'Guédez',     'facturador', None),
]
# Peso relativo de ventas por vendedor (unos venden más que otros)
PESO_VENDEDOR = {
    'vendedor.luis': 1.4, 'vendedor.karla': 1.1, 'vendedor.jesus': 0.8,
    'vendedor.marielys': 1.3, 'vendedor.orlando': 0.9, 'vendedor.yusmary': 0.7,
}

# (categoría, nombre, precio USD, peso kg, stock mínimo)
PRODUCTOS = [
    ('Harinas y granos', 'Harina de maíz precocida 1kg (bulto 20)', 21.50, 20, 60),
    ('Harinas y granos', 'Harina de trigo todo uso 1kg (bulto 20)', 24.00, 20, 40),
    ('Harinas y granos', 'Arroz blanco tipo I 1kg (bulto 24)', 23.00, 24, 60),
    ('Harinas y granos', 'Pasta larga 1kg (bulto 12)', 13.80, 12, 50),
    ('Harinas y granos', 'Pasta corta 500g (bulto 24)', 14.40, 12, 40),
    ('Harinas y granos', 'Caraotas negras 500g (bulto 24)', 19.20, 12, 30),
    ('Harinas y granos', 'Azúcar refinada 1kg (bulto 20)', 20.00, 20, 50),
    ('Aceites y grasas', 'Aceite vegetal 1L (caja 12)', 30.00, 11, 40),
    ('Aceites y grasas', 'Margarina 500g (caja 24)', 33.60, 12, 25),
    ('Aceites y grasas', 'Mayonesa 445g (caja 12)', 26.40, 6, 20),
    ('Enlatados', 'Atún en aceite 140g (caja 48)', 52.80, 8, 20),
    ('Enlatados', 'Sardinas en salsa 170g (caja 48)', 31.20, 9, 25),
    ('Enlatados', 'Maíz dulce 300g (caja 24)', 26.40, 8, 15),
    ('Enlatados', 'Salsa de tomate 397g (caja 24)', 24.00, 10, 20),
    ('Lácteos', 'Leche en polvo completa 400g (caja 24)', 86.40, 10, 20),
    ('Lácteos', 'Queso blanco llanero (kg)', 6.50, 1, 80),
    ('Lácteos', 'Mantequilla 250g (caja 20)', 44.00, 5, 15),
    ('Bebidas', 'Refresco cola 2L (paca 6)', 7.80, 12, 80),
    ('Bebidas', 'Agua mineral 1.5L (paca 6)', 4.20, 9, 80),
    ('Bebidas', 'Jugo de naranja 1L (caja 12)', 18.00, 12, 30),
    ('Bebidas', 'Café molido 500g (caja 12)', 54.00, 6, 20),
    ('Limpieza', 'Detergente en polvo 1kg (bulto 12)', 27.60, 12, 30),
    ('Limpieza', 'Jabón de panela (caja 50)', 22.50, 10, 25),
    ('Limpieza', 'Cloro 1L (caja 12)', 10.80, 13, 30),
    ('Limpieza', 'Lavaplatos en crema 500g (caja 24)', 28.80, 12, 20),
    ('Cuidado personal', 'Papel higiénico 4 rollos (bulto 12)', 19.20, 6, 40),
    ('Cuidado personal', 'Jabón de tocador 110g (caja 72)', 43.20, 8, 15),
    ('Cuidado personal', 'Crema dental 100ml (caja 72)', 64.80, 9, 15),
    ('Cuidado personal', 'Champú 400ml (caja 12)', 34.80, 6, 15),
    ('Snacks y galletas', 'Galletas de soda (caja 12)', 15.60, 5, 25),
    ('Snacks y galletas', 'Galletas dulces surtidas (caja 24)', 21.60, 6, 20),
    ('Snacks y galletas', 'Chocolate de taza 125g (caja 36)', 39.60, 5, 15),
]

CLIENTES = [
    # (nombre, ciudad, zona, tamaño 1-3)
    ('Supermercado El Llanero', 'Guanare', 'Norte', 3),
    ('Abastos La Portuguesa', 'Guanare', 'Norte', 2),
    ('Bodega Don Chepe', 'Guanare', 'Norte', 1),
    ('Comercial Santa Rosalía', 'Guanare', 'Norte', 2),
    ('Supermercado Coromoto', 'Guanare', 'Norte', 3),
    ('Abastos Mi Tierra', 'Acarigua', 'Norte', 2),
    ('Automercado Araure Center', 'Araure', 'Norte', 3),
    ('Bodega Los Samanes', 'Acarigua', 'Norte', 1),
    ('Distribuidora El Parque', 'Acarigua', 'Norte', 2),
    ('Víveres La Esperanza', 'Araure', 'Norte', 1),
    ('Supermercado Payara', 'Ospino', 'Norte', 2),
    ('Abastos Hermanos Linárez', 'Ospino', 'Norte', 1),
    ('Comercial Biscucuy', 'Biscucuy', 'Norte', 2),
    ('Bodega La Chinita', 'Biscucuy', 'Norte', 1),
    ('Mercado Popular Chabasquén', 'Chabasquén', 'Norte', 1),
    ('Supermercado Turén Plaza', 'Villa Bruzual', 'Norte', 3),
    ('Abastos El Trigal', 'Villa Bruzual', 'Norte', 1),
    ('Víveres Doña Carmen', 'Píritu', 'Norte', 1),
    ('Comercial Papelón', 'Papelón', 'Norte', 1),
    ('Inversiones Morichal', 'Guanare', 'Norte', 2),
    ('Supermercado Barinas Real', 'Barinas', 'Sur', 3),
    ('Automercado Alto Barinas', 'Barinas', 'Sur', 3),
    ('Abastos La Barinesa', 'Barinas', 'Sur', 2),
    ('Bodega El Cabimo', 'Barinas', 'Sur', 1),
    ('Comercial Obispos', 'Obispos', 'Sur', 2),
    ('Víveres Santa Bárbara', 'Santa Bárbara', 'Sur', 1),
    ('Supermercado Socopó', 'Socopó', 'Sur', 2),
    ('Abastos Barrancas', 'Barrancas', 'Sur', 1),
    ('Distribuidora Sabaneta', 'Sabaneta', 'Sur', 2),
    ('Bodega Los Mangos', 'Sabaneta', 'Sur', 1),
    ('Mercado Municipal Pedraza', 'Ciudad Bolivia', 'Sur', 1),
    ('Supermercado Barinitas', 'Barinitas', 'Sur', 2),
    ('Abastos El Samán', 'Barinitas', 'Sur', 1),
    ('Comercial San Silvestre', 'San Silvestre', 'Sur', 1),
    ('Inversiones Torunos', 'Torunos', 'Sur', 1),
    ('Supermercado Guanarito', 'Guanarito', 'Sur', 2),
    ('Abastos Las Palmas', 'Guanarito', 'Sur', 1),
    ('Víveres El Baúl', 'El Baúl', 'Sur', 1),
    ('Comercial Tucupido', 'Tucupido', 'Sur', 1),
    ('Automercado Mi Llano', 'Barinas', 'Sur', 3),
]
MOROSOS = {'Bodega Don Chepe', 'Comercial Papelón', 'Bodega El Cabimo', 'Víveres El Baúl'}

COMPETIDORES = ['Distribuidora Occidente', 'Comercial Mayorista Andes', 'Alimentos del Llano C.A.',
                'Grupo Distribuidor Centro', 'Mayor Portuguesa']

# Estacionalidad por mes (1-12): diciembre alto, enero-febrero bajos
ESTACIONALIDAD = {1: 0.78, 2: 0.84, 3: 0.95, 4: 0.97, 5: 1.0, 6: 0.98,
                  7: 1.02, 8: 0.92, 9: 1.05, 10: 1.08, 11: 1.18, 12: 1.38}
DIAS_RUTA = {'Norte': (0, 2, 4), 'Sur': (1, 3)}
MESES_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
            'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _d(valor):
    """Decimal con 2 decimales."""
    return Decimal(str(valor)).quantize(CENT, rounding=ROUND_HALF_UP)


def _inicio_mes(fecha, meses_atras):
    y, m = divmod(fecha.year * 12 + fecha.month - 1 - meses_atras, 12)
    return datetime.date(y, m + 1, 1)


def _dias_del_mes(primer_dia):
    siguiente = _inicio_mes(primer_dia, -1)
    return (siguiente - primer_dia).days


class Command(BaseCommand):
    help = 'Crea una organización demo con historia larga para ver gráficas de largo plazo.'

    def add_arguments(self, parser):
        parser.add_argument('--meses', type=int, default=24, help='Meses de historia (default 24)')
        parser.add_argument('--reset', action='store_true', help='Borra la org demo y la recrea')
        parser.add_argument('--reset-passwords', action='store_true',
                            help='Regenera las contraseñas de los usuarios demo existentes')
        parser.add_argument('--superadmin', default='simon',
                            help='Username del superadmin de la plataforma (default: simon)')
        parser.add_argument('--seed', type=int, default=2026, help='Semilla aleatoria')

    def handle(self, *args, **opts):
        random.seed(opts['seed'])
        self.hoy = timezone.localdate()
        self.credenciales = []
        self.claves_env = json.loads(os.environ.get('SEED_CREDENCIALES') or '{}')

        if opts['reset']:
            self._borrar_org()

        if Organization.objects.filter(slug=ORG_SLUG).exists():
            self.stdout.write(self.style.WARNING(
                f'La organización {ORG_SLUG} ya existe. Usa --reset para regenerarla.'))
            self._usuarios_plataforma(opts)
            self._imprimir_credenciales()
            return

        with transaction.atomic():
            self.org = Organization.objects.create(name=ORG_NOMBRE, slug=ORG_SLUG, plan='pro', is_active=True)
            self._usuarios(opts)
            self._usuarios_plataforma(opts)
            self._maestros()
            self._tasas(opts['meses'])
            self._pedidos(opts['meses'])
            self._facturas_y_pagos()
            self._viajes()
            self._inventario()
            self._cotizaciones(opts['meses'])
            self._visitas(opts['meses'])
            self._devoluciones()
            self._competencia(opts['meses'])
            self._cuotas()

        self._resumen()
        self._imprimir_credenciales()

    # ── Borrado ────────────────────────────────────────────────────────────
    def _borrar_org(self):
        org = Organization.objects.filter(slug=ORG_SLUG).first()
        if not org:
            return
        with transaction.atomic():
            DevolucionItem.objects.filter(organization=org).delete()
            Devolucion.objects.filter(organization=org).delete()
            ViajeDetalle.objects.filter(organization=org).delete()
            Viaje.objects.filter(organization=org).delete()
            Vehiculo.objects.filter(organization=org).delete()
            Pago.objects.filter(organization=org).delete()
            Cotizacion.objects.filter(organization=org).update(pedido_generado=None)
            CotizacionItem.objects.filter(organization=org).delete()
            Cotizacion.objects.filter(organization=org).delete()
            VisitaComercial.objects.filter(organization=org).delete()
            CompetenciaRegistro.objects.filter(organization=org).delete()
            Pedido.objects.filter(organization=org).delete()
            Cliente.all_objects.filter(organization=org).delete()
            MovimientoInventario.objects.filter(organization=org).delete()
            Lote.objects.filter(organization=org).delete()
            Producto.all_objects.filter(organization=org).delete()
            CategoriaProducto.objects.filter(organization=org).delete()
            VentaMensual.objects.filter(organization=org).delete()
            Zona.objects.filter(organization=org).delete()
            TasaCuotas.objects.filter(organization=org).delete()
            TasaConfig.objects.filter(organization=org).delete()
            ZonaDespacho.objects.filter(organization=org).delete()
            MetodoPago.objects.filter(organization=org).delete()
            User.objects.filter(organization=org).delete()
            org.delete()
        self.stdout.write(self.style.WARNING(f'  Reset: organización {ORG_SLUG} eliminada.'))

    # ── Usuarios ───────────────────────────────────────────────────────────
    def _crear_usuario(self, username, first, last, role, org, reset_pw, **extra):
        user = User.objects.filter(username=username).first()
        nuevo = user is None
        if nuevo:
            user = User(username=username)
        user.first_name, user.last_name, user.role = first, last, role
        user.organization = org
        user.email = f'{username}@demo.smartsolutions.com.ve'
        user.is_active = True
        for k, v in extra.items():
            setattr(user, k, v)
        if nuevo or reset_pw:
            if username in self.claves_env:
                user.set_password(self.claves_env[username])
            else:
                clave = secrets.token_urlsafe(9)
                user.set_password(clave)
                self.credenciales.append((username, user.get_role_display(), clave,
                                          org.name if org else 'Plataforma (todas)'))
        user.save()
        return user

    def _usuarios(self, opts):
        self.users = {}
        for username, first, last, role, zona in USUARIOS:
            self.users[username] = self._crear_usuario(
                username, first, last, role, self.org, opts['reset_passwords'])
        # Vendedores rinden cuentas a su supervisor de zona
        sup = {'Norte': self.users['supervisor.norte'], 'Sur': self.users['supervisor.sur']}
        self.zona_de = {}
        for username, _f, _l, role, zona in USUARIOS:
            if role == 'vendedor':
                u = self.users[username]
                u.supervisor_asignado = sup[zona]
                u.save(update_fields=['supervisor_asignado'])
                self.zona_de[username] = zona
        self.vendedores = [self.users[u] for u in PESO_VENDEDOR]

    def _usuarios_plataforma(self, opts):
        self._crear_usuario(opts['superadmin'], 'Simón', 'Briceño', 'superadmin', None,
                            opts['reset_passwords'], is_staff=True, is_superuser=True)

    # ── Maestros ───────────────────────────────────────────────────────────
    def _maestros(self):
        org = self.org
        self.zonas = {n: Zona.objects.create(organization=org, nombre=n, codigo=n[:3].upper())
                      for n in ('Norte', 'Sur')}
        self.zonas_despacho = {
            'Norte': ZonaDespacho.objects.create(organization=org, nombre='Portuguesa',
                                                 costo_base_flete=_d(35), dias_entrega_estimados=2),
            'Sur': ZonaDespacho.objects.create(organization=org, nombre='Barinas',
                                               costo_base_flete=_d(55), dias_entrega_estimados=3),
        }
        self.metodos = {
            'CONTADO': MetodoPago.objects.create(organization=org, nombre='Contado', tipo='CONTADO', dias_credito=0),
            'CREDITO15': MetodoPago.objects.create(organization=org, nombre='Crédito 15 días', tipo='CREDITO', dias_credito=15),
            'CREDITO30': MetodoPago.objects.create(organization=org, nombre='Crédito 30 días', tipo='CREDITO', dias_credito=30),
        }
        cats = {}
        self.productos = []
        for i, (cat, nombre, precio, peso, minimo) in enumerate(PRODUCTOS, start=1):
            if cat not in cats:
                cats[cat] = CategoriaProducto.objects.create(organization=org, nombre=cat)
            self.productos.append(Producto.objects.create(
                organization=org, nombre=nombre, sku=f'LL-{i:03d}', categoria=cats[cat],
                precio_base=_d(precio), unidad='unidad', peso_kg=_d(peso),
                stock_minimo=_d(minimo), is_active=True,
            ))
        # Popularidad: los básicos (harina, arroz, aceite) se venden más
        self.pop_producto = [3.0 if p.nombre.startswith(('Harina de maíz', 'Arroz', 'Aceite', 'Azúcar', 'Pasta larga'))
                             else random.uniform(0.6, 1.6) for p in self.productos]

        self.clientes = []
        self.meta_cliente = {}
        for nombre, ciudad, zona, tam in CLIENTES:
            dias = random.choice([0, 15, 15, 30]) if tam > 1 else random.choice([0, 0, 15])
            limite = {1: 1500, 2: 6000, 3: 15000}[tam] if dias else 0
            c = Cliente.objects.create(
                organization=org, nombre=nombre, contacto=random.choice(
                    ['Sr. ', 'Sra. ']) + random.choice(['Pérez', 'González', 'Rodríguez', 'Mendoza', 'Suárez', 'Torres']),
                telefono=f'04{random.choice(["12", "14", "16", "24"])}-{random.randint(100, 999)}-{random.randint(1000, 9999)}',
                direccion=f'{ciudad}, estado {"Portuguesa" if zona == "Norte" else "Barinas"}',
                limite_credito=_d(limite), dias_credito=dias,
            )
            self.clientes.append(c)
            self.meta_cliente[c.pk] = {'zona': zona, 'tam': tam, 'dias': dias,
                                       'moroso': nombre in MOROSOS}

    # ── Tasas BCV ──────────────────────────────────────────────────────────
    def _tasas(self, meses):
        inicio = _inicio_mes(self.hoy, meses - 1)
        total_dias = (self.hoy - inicio).days or 1
        tasa_ini, tasa_fin = 38.0, 176.0
        fecha = inicio
        cuotas, config = [], []
        while fecha <= self.hoy:
            t = (fecha - inicio).days / total_dias
            tasa = tasa_ini * (tasa_fin / tasa_ini) ** t * random.uniform(0.985, 1.015)
            cuotas.append(TasaCuotas(organization=self.org, fecha=fecha, tasa_bs_por_usd=Decimal(f'{tasa:.4f}'), fuente='BCV'))
            config.append(TasaConfig(organization=self.org, fecha=fecha, tasa=Decimal(f'{tasa:.4f}'),
                                     activa=(fecha + datetime.timedelta(days=7) > self.hoy),
                                     creado_por=self.users['admin.llanos']))
            fecha += datetime.timedelta(days=7)
        TasaCuotas.objects.bulk_create(cuotas)
        TasaConfig.objects.bulk_create(config)

    # ── Pedidos ────────────────────────────────────────────────────────────
    def _estado_por_edad(self, dias):
        if dias > 30:
            opciones = [('Entregado', 90), ('Cancelado', 10)]
        elif dias > 7:
            opciones = [('Entregado', 60), ('En Proceso', 15), ('Confirmado', 10), ('Cancelado', 8), ('Pendiente', 7)]
        else:
            opciones = [('Pendiente', 35), ('Confirmado', 30), ('En Proceso', 20), ('Entregado', 10), ('Cancelado', 5)]
        return random.choices([e for e, _ in opciones], weights=[w for _, w in opciones])[0]

    def _pedidos(self, meses):
        org = self.org
        despacho = {
            'Entregado': ['Despachado'], 'Cancelado': ['Pendiente Despacho'],
            'Pendiente': ['Pendiente Despacho'], 'Confirmado': ['Pendiente Despacho', 'Programado'],
            'En Proceso': ['Programado', 'En Tránsito'],
        }
        clientes_por_zona = defaultdict(list)
        for c in self.clientes:
            clientes_por_zona[self.meta_cliente[c.pk]['zona']].append(c)
        vendedor_peso = [PESO_VENDEDOR[v.username] for v in self.vendedores]

        self.pedidos = []
        for idx in range(meses):
            primer_dia = _inicio_mes(self.hoy, meses - 1 - idx)
            n_dias = _dias_del_mes(primer_dia)
            if primer_dia.year == self.hoy.year and primer_dia.month == self.hoy.month:
                n_dias = self.hoy.day
            # Crecimiento ~55% en el período + estacionalidad + ruido
            base = 70 * (1 + 0.55 * idx / max(meses - 1, 1))
            n = int(base * ESTACIONALIDAD[primer_dia.month] * random.uniform(0.92, 1.08)
                    * n_dias / _dias_del_mes(primer_dia))
            inflacion = 1 + 0.004 * idx  # precios en USD suben ~0.4% mensual
            for _ in range(n):
                fecha = primer_dia + datetime.timedelta(days=random.randrange(n_dias))
                if fecha.weekday() == 6:  # domingo sin ventas
                    fecha -= datetime.timedelta(days=1)
                vendedor = random.choices(self.vendedores, weights=vendedor_peso)[0]
                cliente = random.choice(clientes_por_zona[self.zona_de[vendedor.username]])
                meta = self.meta_cliente[cliente.pk]
                estado = self._estado_por_edad((self.hoy - fecha).days)
                zona = meta['zona']
                metodo = self.metodos['CONTADO' if not meta['dias'] else f'CREDITO{meta["dias"]}']
                # Rutas fijas: Portuguesa (Norte) lun-mié-vie, Barinas (Sur) mar-jue
                entrega = fecha + datetime.timedelta(days=1)
                while entrega.weekday() not in DIAS_RUTA[zona]:
                    entrega += datetime.timedelta(days=1)
                pedido = Pedido.objects.create(
                    organization=org, numero=generar_numero_pedido(org), fecha_pedido=fecha,
                    fecha_entrega=None if estado == 'Cancelado' else entrega,
                    cliente=cliente, vendedor=vendedor, created_by=vendedor, estado=estado,
                    estado_despacho=random.choice(despacho[estado]), metodo_pago=metodo,
                    zona_despacho=self.zonas_despacho[zona],
                    observaciones=random.choice(['', '', '', 'Entregar en horario de mañana.',
                                                 'Cliente pide factura fiscal.', 'Confirmar antes de despachar.']),
                )
                items = []
                elegidos = random.choices(range(len(self.productos)), weights=self.pop_producto,
                                          k=random.randint(2, 4 + meta['tam'] * 2))
                for pi in set(elegidos):
                    p = self.productos[pi]
                    cant = random.randint(1, 6) * meta['tam'] * (3 if p.nombre.startswith('Queso') else 1)
                    precio = _d(float(p.precio_base) * inflacion * random.uniform(0.97, 1.03))
                    items.append(PedidoItem(organization=org, pedido=pedido, producto=p.nombre,
                                            sku=p.sku, cantidad=_d(cant), precio=precio))
                PedidoItem.objects.bulk_create(items)
                pedido.recalcular_total()
                Pedido.objects.filter(pk=pedido.pk).update(
                    created_at=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(9, 0)))
                    + datetime.timedelta(minutes=random.randint(0, 540)))
                pedido._items = items
                self.pedidos.append(pedido)

    # ── Facturas y cobranza ───────────────────────────────────────────────
    def _facturas_y_pagos(self):
        org = self.org
        facturas, pagos = [], []
        admin = self.users['admin.llanos']
        n_fac = 1
        for p in self.pedidos:
            if p.estado != 'Entregado':
                continue
            facturas.append(Factura(organization=org, pedido=p, numero_factura=f'FAC-{n_fac:06d}',
                                    fecha_factura=p.fecha_entrega, monto=p.total, created_by=admin))
            n_fac += 1
            meta = self.meta_cliente[p.cliente_id]
            fecha_pago = p.fecha_entrega + datetime.timedelta(days=meta['dias'] + random.randint(-3, 10))
            if meta['moroso']:
                fecha_pago += datetime.timedelta(days=random.randint(20, 70))
            if fecha_pago > self.hoy:
                continue
            fraccion = Decimal('1') if not meta['moroso'] or random.random() < 0.6 else _d(random.uniform(0.3, 0.8))
            monto = _d(p.total * fraccion)
            pagos.append(Pago(organization=org, cliente_id=p.cliente_id, fecha=fecha_pago, monto=monto,
                              metodo=random.choice(['TRANSFERENCIA'] * 5 + ['ZELLE', 'EFECTIVO', 'DIVISA']),
                              referencia=f'REF{random.randint(10000000, 99999999)}',
                              observaciones=f'Pago pedido {p.numero}', registrado_por=admin))
        Factura.objects.bulk_create(facturas)
        Pago.objects.bulk_create(pagos)
        # Pagos de contado de pedidos aún no entregados no se registran: quedan en CxC.

    # ── Flota ──────────────────────────────────────────────────────────────
    def _viajes(self):
        org = self.org
        choferes = [self.users[u] for u in ('chofer.ramon', 'chofer.wilmer', 'chofer.eduardo')]
        vehiculos = [
            Vehiculo.objects.create(organization=org, placa='A12BC3D', marca='Chevrolet', modelo='NPR',
                                    capacidad_kg=_d(1500), chofer_habitual=choferes[0]),
            Vehiculo.objects.create(organization=org, placa='A45EF6G', marca='Ford', modelo='Cargo 815',
                                    capacidad_kg=_d(3500), chofer_habitual=choferes[1]),
            Vehiculo.objects.create(organization=org, placa='A78HI9J', marca='Iveco', modelo='Tector',
                                    capacidad_kg=_d(8000), chofer_habitual=choferes[2]),
        ]
        peso_prod = {p.nombre: float(p.peso_kg) for p in self.productos}
        por_dia = defaultdict(list)
        for p in self.pedidos:
            if p.estado in ('Entregado', 'En Proceso') and p.fecha_entrega:
                por_dia[(p.fecha_entrega, p.zona_despacho_id)].append(p)
        detalles = []
        vehiculos_por_capacidad = sorted(vehiculos, key=lambda v: v.capacidad_kg)
        for (fecha, _zona), pedidos in sorted(por_dia.items(), key=lambda x: x[0][0]):
            estado = 'Completado' if fecha < self.hoy else ('En Ruta' if fecha == self.hoy else 'Programado')
            pesos = [(p, min(sum(float(it.cantidad) * peso_prod.get(it.producto, 5) for it in p._items),
                             float(vehiculos_por_capacidad[-1].capacidad_kg))) for p in pedidos]
            pendientes = pesos
            while pendientes:
                carga_total = sum(w for _, w in pendientes)
                # El vehículo más pequeño donde cabe todo lo pendiente; si no cabe, el más grande
                v = next((v for v in vehiculos_por_capacidad if float(v.capacidad_kg) >= carga_total),
                         vehiculos_por_capacidad[-1])
                viaje = Viaje.objects.create(
                    organization=org, vehiculo=v, chofer=v.chofer_habitual, fecha=fecha, estado=estado,
                    km_recorridos=_d(random.uniform(60, 320)) if estado == 'Completado' else None,
                    costo_flete=_d(random.uniform(40, 160)), created_by=self.users['admin.llanos'])
                carga, resto = 0.0, []
                for p, w in pendientes:
                    if carga + w <= float(v.capacidad_kg):
                        carga += w
                        detalles.append(ViajeDetalle(organization=org, viaje=viaje, pedido=p,
                                                     peso_estimado_kg=_d(w)))
                    else:
                        resto.append((p, w))
                pendientes = resto
        ViajeDetalle.objects.bulk_create(detalles)

    # ── Inventario ─────────────────────────────────────────────────────────
    def _inventario(self):
        org = self.org
        vendido = defaultdict(Decimal)
        for p in self.pedidos:
            if p.estado != 'Cancelado':
                for it in p._items:
                    vendido[it.producto] += it.cantidad
        lotes, movs = [], []
        for i, p in enumerate(self.productos):
            total = vendido[p.nombre]
            # stock actual: la mayoría sobre el mínimo, ~20% por debajo para generar alertas
            if random.random() < 0.2:
                actual = _d(float(p.stock_minimo) * random.uniform(0.2, 0.8))
            else:
                actual = _d(float(p.stock_minimo) * random.uniform(1.5, 4))
            costo = _d(float(p.precio_base) * 0.74)
            historico = Lote(organization=org, producto=p, codigo_lote=f'L{i + 1:03d}-A',
                             fecha_elaboracion=self.hoy - datetime.timedelta(days=700),
                             fecha_caducidad=self.hoy + datetime.timedelta(days=random.randint(-30, 60)),
                             cantidad_inicial=total, cantidad_disponible=Decimal('0'), costo_unitario=costo,
                             is_active=False)
            vigente = Lote(organization=org, producto=p, codigo_lote=f'L{i + 1:03d}-B',
                           fecha_elaboracion=self.hoy - datetime.timedelta(days=30),
                           fecha_caducidad=self.hoy + datetime.timedelta(days=random.randint(20, 400)),
                           cantidad_inicial=actual, cantidad_disponible=actual, costo_unitario=costo)
            lotes += [historico, vigente]
        Lote.objects.bulk_create(lotes)
        for lote in lotes:
            movs.append(MovimientoInventario(organization=org, lote=lote, tipo='ENTRADA',
                                             cantidad=lote.cantidad_inicial, referencia='Carga demo',
                                             created_by=self.users['admin.llanos']))
            if not lote.is_active and lote.cantidad_inicial:
                movs.append(MovimientoInventario(organization=org, lote=lote, tipo='SALIDA',
                                                 cantidad=-lote.cantidad_inicial, referencia='Ventas históricas',
                                                 created_by=self.users['admin.llanos']))
        MovimientoInventario.objects.bulk_create(movs)

    # ── Cotizaciones ───────────────────────────────────────────────────────
    def _cotizaciones(self, meses):
        from apps.configuracion.models import ConfiguracionEmpresa
        org = self.org
        config = ConfiguracionEmpresa.objects.get(organization=org)
        disponibles = defaultdict(list)
        for p in self.pedidos:
            if p.estado != 'Cancelado':
                disponibles[p.cliente_id].append(p)
        for idx in range(meses):
            primer_dia = _inicio_mes(self.hoy, meses - 1 - idx)
            for _ in range(random.randint(14, 26)):
                fecha = primer_dia + datetime.timedelta(days=random.randrange(_dias_del_mes(primer_dia)))
                if fecha > self.hoy:
                    continue
                edad = (self.hoy - fecha).days
                if edad < 10:
                    estado = random.choice(['Borrador', 'Enviada', 'Enviada', 'Aceptada'])
                else:
                    estado = random.choices(['Convertida', 'Rechazada', 'Vencida', 'Aceptada'],
                                            weights=[45, 25, 25, 5])[0]
                vendedor = random.choice(self.vendedores)
                cliente = random.choice(self.clientes)
                pedido = None
                if estado == 'Convertida':
                    candidatos = [p for p in disponibles[cliente.pk] if 0 <= (p.fecha_pedido - fecha).days <= 10]
                    if candidatos:
                        pedido = candidatos[0]
                        disponibles[cliente.pk].remove(pedido)
                    else:
                        estado = 'Vencida'
                cot = Cotizacion.objects.create(
                    organization=org, numero=config.get_numero_cotizacion(), fecha=fecha,
                    fecha_vencimiento=fecha + datetime.timedelta(days=15), cliente=cliente, vendedor=vendedor,
                    estado=estado, pedido_generado=pedido, created_by=vendedor)
                items = []
                for p in random.sample(self.productos, random.randint(2, 6)):
                    items.append(CotizacionItem(organization=org, cotizacion=cot, producto=p.nombre, sku=p.sku,
                                                cantidad=_d(random.randint(2, 20)),
                                                precio=_d(float(p.precio_base) * (1 + 0.004 * idx))))
                CotizacionItem.objects.bulk_create(items)
                cot.recalcular_total()

    # ── Visitas ────────────────────────────────────────────────────────────
    def _visitas(self, meses):
        org = self.org
        visitas = []
        inicio = _inicio_mes(self.hoy, meses - 1)
        clientes_por_zona = defaultdict(list)
        for c in self.clientes:
            clientes_por_zona[self.meta_cliente[c.pk]['zona']].append(c)
        for v in self.vendedores:
            fecha = inicio
            while fecha <= self.hoy + datetime.timedelta(days=14):
                if fecha.weekday() < 5 and random.random() < 0.55:
                    futura = fecha > self.hoy
                    estado = 'pendiente' if futura else random.choices(['realizada', 'cancelada'], weights=[86, 14])[0]
                    visitas.append(VisitaComercial(
                        organization=org, cliente=random.choice(clientes_por_zona[self.zona_de[v.username]]),
                        vendedor=v, fecha=fecha, tipo=random.choices(['presencial', 'telefonica', 'virtual'],
                                                                     weights=[70, 22, 8])[0],
                        estado=estado,
                        objetivo=random.choice(['Toma de pedido', 'Cobranza', 'Presentar promoción del mes',
                                                'Revisar exhibición en anaquel', 'Seguimiento de cotización']),
                        resultado='' if estado != 'realizada' else random.choice(
                            ['Pedido tomado.', 'Cliente pagó factura pendiente.', 'Interesado en nueva línea.',
                             'Sin compra esta semana.', 'Solicita mejor precio en aceite.']),
                    ))
                fecha += datetime.timedelta(days=1)
        VisitaComercial.objects.bulk_create(visitas)

    # ── Devoluciones ───────────────────────────────────────────────────────
    def _devoluciones(self):
        org = self.org
        gerente = self.users['gerente.llanos']
        for p in self.pedidos:
            if p.estado != 'Entregado' or random.random() > 0.025:
                continue
            it = random.choice(p._items)
            cant = _d(max(1, int(float(it.cantidad) * random.uniform(0.1, 0.5))))
            edad = (self.hoy - p.fecha_entrega).days
            estado = random.choice(['Pendiente', 'Aprobada']) if edad < 7 else random.choices(
                ['Completada', 'Rechazada'], weights=[80, 20])[0]
            dev = Devolucion.objects.create(
                organization=org, pedido=p, cliente_id=p.cliente_id,
                fecha=min(p.fecha_entrega + datetime.timedelta(days=random.randint(1, 6)), self.hoy),
                motivo=random.choice(['DEFECTO', 'ERROR_PEDIDO', 'DANO_TRANSPORTE', 'VENCIDO']),
                estado=estado, monto_credito=_d(cant * it.precio) if estado == 'Completada' else Decimal('0'),
                reingresar_inventario=False, registrado_por=p.vendedor,
                aprobado_por=gerente if estado in ('Aprobada', 'Completada', 'Rechazada') else None,
                observaciones='Generado por seed histórico')
            DevolucionItem.objects.create(organization=org, devolucion=dev, producto=it.producto, sku=it.sku,
                                          cantidad=cant, precio_unitario=it.precio)

    # ── Competencia ────────────────────────────────────────────────────────
    def _competencia(self, meses):
        org = self.org
        regs = []
        for idx in range(meses):
            primer_dia = _inicio_mes(self.hoy, meses - 1 - idx)
            for _ in range(random.randint(3, 8)):
                fecha = primer_dia + datetime.timedelta(days=random.randrange(_dias_del_mes(primer_dia)))
                if fecha > self.hoy:
                    continue
                p = random.choice(self.productos)
                nuestro = float(p.precio_base) * (1 + 0.004 * idx)
                regs.append(CompetenciaRegistro(
                    organization=org, fecha=fecha, cliente=random.choice(self.clientes),
                    vendedor=random.choice(self.vendedores), producto=p.nombre,
                    competidor=random.choice(COMPETIDORES), precio_comp=_d(nuestro * random.uniform(0.9, 1.08)),
                    precio_nuestro=_d(nuestro),
                    accion_tomada=random.choice(['Se mantuvo precio por volumen.', 'Se ofreció 3% de descuento.',
                                                 'Cliente prefiere nuestro crédito.', 'Monitorear.'])))
        CompetenciaRegistro.objects.bulk_create(regs)

    # ── Cuotas (plan vs real) ──────────────────────────────────────────────
    def _cuotas(self):
        org = self.org
        real = defaultdict(lambda: [Decimal('0'), Decimal('0')])  # (cantidad, venta usd)
        tasa_mes = {}
        for t in TasaCuotas.objects.filter(organization=org).order_by('fecha'):
            tasa_mes[t.fecha.replace(day=1)] = t.tasa_bs_por_usd
        for p in self.pedidos:
            if p.estado == 'Cancelado':
                continue
            periodo = p.fecha_pedido.replace(day=1)
            for it in p._items:
                acc = real[(periodo, p.vendedor_id, it.producto)]
                acc[0] += it.cantidad
                acc[1] += it.cantidad * it.precio
        productos = {p.nombre: p for p in self.productos}
        vendedores = {v.pk: v for v in self.vendedores}
        filas = []
        for (periodo, vid, nombre), (cant, venta) in real.items():
            v, prod = vendedores[vid], productos[nombre]
            zona = self.zona_de[v.username]
            factor_plan = Decimal(str(round(random.uniform(0.88, 1.18), 3)))
            plan_venta = _d(venta * factor_plan)
            costo = _d(venta * Decimal('0.74'))
            flete = _d(venta * Decimal('0.03'))
            gastos = _d(venta * Decimal('0.06'))
            filas.append(VentaMensual(
                organization=org, periodo=periodo, vendedor=v, vendedor_nombre=v.get_full_name(),
                producto=prod, producto_nombre=nombre, codigo_producto=prod.sku, zona=self.zonas[zona],
                zona_nombre=zona, canal='DIRECTO', distribucion='Propia',
                plan_cantidad=_d(cant * factor_plan), plan_precio_usd=prod.precio_base, plan_venta_usd=plan_venta,
                plan_costo_usd=_d(plan_venta * Decimal('0.74')), plan_margen_usd=_d(plan_venta * Decimal('0.26')),
                plan_margen_neto_usd=_d(plan_venta * Decimal('0.17')),
                real_cantidad=_d(cant), real_venta_usd=_d(venta),
                real_venta_ves=_d(venta * tasa_mes.get(periodo, Decimal('1'))),
                real_costo_usd=costo, real_flete_usd=flete, real_gastos_ventas_usd=gastos,
                real_margen_neto_usd=_d(venta - costo - flete - gastos),
            ))
        VentaMensual.objects.bulk_create(filas, batch_size=1000)

    # ── Salida ─────────────────────────────────────────────────────────────
    def _resumen(self):
        org = self.org
        self.stdout.write(self.style.SUCCESS(f'\n✓ {ORG_NOMBRE} ({ORG_SLUG})'))
        for etiqueta, qs in [
            ('Clientes', Cliente.objects.filter(organization=org)),
            ('Productos', Producto.objects.filter(organization=org)),
            ('Pedidos', Pedido.objects.filter(organization=org)),
            ('Facturas', Factura.objects.filter(organization=org)),
            ('Pagos', Pago.objects.filter(organization=org)),
            ('Viajes', Viaje.objects.filter(organization=org)),
            ('Cotizaciones', Cotizacion.objects.filter(organization=org)),
            ('Visitas', VisitaComercial.objects.filter(organization=org)),
            ('Devoluciones', Devolucion.objects.filter(organization=org)),
            ('Competencia', CompetenciaRegistro.objects.filter(organization=org)),
            ('Cuotas (filas)', VentaMensual.objects.filter(organization=org)),
        ]:
            self.stdout.write(f'  {etiqueta:<15} {qs.count()}')
        primero = Pedido.objects.filter(organization=org).order_by('fecha_pedido').first()
        if primero:
            self.stdout.write(f'  Historia desde  {primero.fecha_pedido} hasta {self.hoy}')

    def _imprimir_credenciales(self):
        if not self.credenciales:
            self.stdout.write('\n  (Sin claves que mostrar: usuarios existentes o claves tomadas de SEED_CREDENCIALES.)')
            return
        self.stdout.write('\nCREDENCIALES (se muestran una sola vez):')
        for username, rol, clave, org in self.credenciales:
            self.stdout.write(f'  {username:<20} {rol:<14} {clave:<16} {org}')
