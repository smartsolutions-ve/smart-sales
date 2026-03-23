# PROMPT FASE 1 — Chat IA en SmartSales Django
> Pasa este archivo completo a Claude Code después del contenido de `CLAUDE.md`

---

## INSTRUCCIÓN INICIAL PARA CLAUDE CODE

Antes de leer la tarea, interioriza estas reglas de trabajo:

- **No escribas código hasta que yo apruebe tu plan.** Al final de este prompt hay una sección de confirmación que debes responder primero.
- **Sigue las convenciones del proyecto** definidas en `CLAUDE.md` sin excepción.
- **Implementa en el orden exacto** indicado en la sección "Orden de implementación".
- **Después de cada bloque**, indica qué archivos creaste/modificaste y qué viene a continuación.
- **Si encuentras una ambigüedad**, pregunta antes de asumir.

---

## CONTEXTO DEL PROYECTO

Trabajas en **SmartSales**, un SaaS multi-tenant construido con:

| Capa | Tecnología |
|---|---|
| Backend | Django 5.2 + Python 3.13 |
| Base de datos | SQLite (dev) / PostgreSQL 16 (prod) |
| Frontend | Django Templates + HTMX 2.0.4 + Alpine.js v3 + Tailwind CSS (CDN) |
| Auth | Django Auth integrado (AbstractUser) |
| PDF | WeasyPrint 68.1 |
| Deploy | Docker + Nginx + DigitalOcean Droplet |
| Tests | pytest-django + factory_boy (90 tests pasando) |
| Email | django-anymail + Resend (console backend en dev) |

### Multi-tenancy — regla crítica

**TODOS los modelos tenant-specific tienen un FK `organization`.** El middleware `TenantMiddleware` inyecta `request.org` en cada request. Todas las queries DEBEN filtrar por `organization=request.org`. Un bug de tenant en producción es el error más grave posible en este sistema.

**IMPORTANTE:** `request.org` es `None` para superadmins. Cualquier vista que acceda a `request.org` debe verificar primero con `if not request.org` y retornar querysets vacíos o manejar el caso apropiadamente.

```python
# ✅ CORRECTO — siempre así
Pedido.objects.filter(organization=request.org, ...)

# ❌ INCORRECTO — nunca así
Pedido.objects.filter(...)  # expone datos de otros tenants

# ✅ CORRECTO — manejar superadmin
if not request.org:
    clientes = Cliente.objects.none()
else:
    clientes = Cliente.objects.filter(organization=request.org)
```

La clase base para modelos tenant es:

```python
class TenantModel(models.Model):
    organization = models.ForeignKey('accounts.Organization', on_delete=models.PROTECT)
    class Meta:
        abstract = True
```

### Roles del sistema

| Rol | Acceso relevante |
|---|---|
| `superadmin` | Todo, sin `organization` (request.org = None) |
| `gerente` | Dashboard completo — `can_access_dashboard = True` |
| `vendedor` | Solo `/campo/` — NO tiene acceso al chat IA |

### Decoradores de acceso

```python
@login_required                         # cualquier usuario logueado
@role_required('gerente', 'superadmin') # roles específicos (también permite is_superuser)
@superadmin_required                    # solo superadmin
```

**Nota:** `@role_required` ya permite acceso automático a usuarios con `is_superuser=True` o `is_superadmin=True`, independientemente del campo `role`.

### Modelos existentes que usará el chat

```
apps.pedidos.models:
  - TenantModel (abstract — base para modelos multi-tenant)
  - Pedido (numero, fecha_pedido, fecha_entrega, cliente, vendedor,
            estado, estado_despacho, total, observaciones, ref_competencia,
            created_by, created_at, updated_at)
  - PedidoItem (pedido, producto, sku, cantidad, precio)
    → producto es CharField (nombre histórico, no FK)
    → subtotal es @property: cantidad * precio
  - PedidoLog (pedido, usuario, accion, detalle, created_at)
    → auditoría de cambios en pedidos
  - Cliente (nombre, contacto, telefono, email, direccion)

apps.productos.models:
  - CategoriaProducto (nombre) — hereda TenantModel
  - Producto (nombre, sku, categoria, descripcion, precio_base, unidad, is_active)
    → catálogo de productos, conectado a pedidos vía autocompletado

apps.competencia.models:
  - CompetenciaRegistro (fecha, cliente, vendedor, producto, competidor,
                         precio_comp, precio_nuestro, accion_tomada)
    → diferencia_precio es @property
    → somos_mas_caros es @property

apps.accounts.models:
  - Organization (name, slug, is_active, plan)
    → planes: starter, pro, enterprise
  - User (username, first_name, last_name, email, role, organization)
    → is_superadmin, is_gerente, is_vendedor son @property
    → can_access_dashboard: role in ('superadmin', 'gerente')

apps.pedidos.models (facturación):
  - Factura (pedido FK, numero_factura, fecha_factura, monto, observaciones,
             created_by, created_at)
    → NO hereda TenantModel (org se infiere del pedido)
    → Un pedido puede tener 0, 1 o N facturas
  - Pedido tiene properties nuevas:
    → monto_facturado: suma de facturas.monto
    → estado_facturacion: 'sin_facturar' | 'parcial' | 'facturado'

apps.flotas.models:
  - Vehiculo (TenantModel: placa, marca, modelo, capacidad_kg,
              chofer_habitual FK User, is_active)
  - Viaje (TenantModel: vehiculo FK, chofer FK, fecha, estado, km_recorridos,
           costo_flete, observaciones, created_by)
    → ESTADOS: Programado, En Ruta, Completado, Cancelado
    → peso_total_kg, porcentaje_utilizacion, num_pedidos son @property
  - ViajeDetalle (viaje FK, pedido FK, peso_estimado_kg, orden_entrega)
    → tabla intermedia viaje↔pedido

apps.productos.models (campo nuevo):
  - Producto ahora tiene peso_kg (DecimalField, null, blank)
    → usado para calcular peso de despacho en flotas

apps.cuotas.models:
  - Zona (TenantModel: nombre, codigo)
  - TasaCambio (TenantModel: fecha, tasa_bs_por_usd, fuente)
  - VentaMensual (TenantModel: periodo, vendedor/vendedor_nombre,
                  producto/producto_nombre, codigo_producto, zona/zona_nombre,
                  canal, distribucion)
    → Campos PLAN: plan_cantidad, plan_venta_usd, plan_costo_usd, plan_margen_usd, etc.
    → Campos REAL: real_cantidad, real_venta_usd, real_venta_ves, real_costo_usd, etc.
    → cumplimiento_cantidad, cumplimiento_venta son @property
    → Datos importados desde Excel
```

### Estados de negocio importantes

```python
# Pedido.ESTADOS
['Pendiente', 'Confirmado', 'En Proceso', 'Entregado', 'Cancelado']
# Estados terminales (no pueden cambiar): Entregado, Cancelado

# Pedido.ESTADOS_DESPACHO
['Pendiente Despacho', 'Programado', 'En Tránsito', 'Despachado', 'Devuelto']
# Al marcar Entregado → despacho pasa automáticamente a Despachado

# Pedido.estado_facturacion (property)
# 'sin_facturar' | 'parcial' | 'facturado'

# Viaje.ESTADOS
['Programado', 'En Ruta', 'Completado', 'Cancelado']
```

### Features ya implementadas (no reimplementar)

- Dashboard con 6 gráficas Chart.js + 4 KPIs + filtro de período
- CRUD completo: Pedidos, Clientes, Productos, Competencia
- Despacho Kanban con cambio de estado HTMX
- Formularios móviles para vendedores (campo)
- Exportar CSV: pedidos, reporte vendedores, reporte clientes
- Filtros por rango de fecha: pedidos, reportes
- PDF de pedidos con WeasyPrint
- Auditoría de pedidos (PedidoLog)
- Notificaciones email al cambiar estado de pedido
- Modal de confirmación al eliminar, mensajes auto-cerrables
- Prevención de doble-clic en submit
- Sidebar responsive con overlay mobile
- Perfil de usuario con cambio de contraseña
- Admin panel completo (orgs + usuarios)
- Password reset por email
- Autocompletado de productos en formularios de pedido y competencia
- **Facturación**: Registro de facturas externas por pedido (agregar/eliminar), estado de facturación (sin_facturar/parcial/facturado), badge en tabla de pedidos
- **Flotas**: CRUD de vehículos, CRUD de viajes con asignación de pedidos, barra de utilización de capacidad, dashboard de flotas con métricas
- **Cuotas/Ventas**: Importación de Excel con cuotas plan vs real, resúmenes por zona/vendedor/producto con % cumplimiento, tasas de cambio, exportación CSV

### Patrón de respuesta HTMX en views existentes

```python
def mi_view(request):
    # ...lógica...
    if request.htmx:
        return render(request, 'partials/fragmento.html', context)
    return render(request, 'modulo/pagina_completa.html', context)
```

### Patrón Alpine.js global

`base.html` tiene un Alpine store `appShell()` que expone:
- `darkMode` — toggle de dark mode
- `sidebarOpen` — sidebar mobile
- `confirmModal`, `confirmar()`, `ejecutarConfirmacion()` — modal de confirmación global
- CSRF token inyectado vía `htmx:configRequest` listener

---

## QUÉ DEBES CONSTRUIR

Un módulo `apps/chat_ia/` completo que añada un **asistente de inteligencia artificial** al sistema SmartSales. El asistente:

- Aparece como **botón flotante** en la esquina inferior derecha de todas las páginas del dashboard (visible solo para gerentes y superadmins — usar `user.can_access_dashboard`)
- Consulta los **datos reales de la organización** en tiempo real desde la BD
- Usa **Gemini Flash** como modelo de IA (google-generativeai)
- Guarda el **historial de conversación** en la base de datos (persistente entre sesiones)
- Responde en **lenguaje natural en español** sobre el negocio del cliente
- Está diseñado para **escalar a escritura** (registrar/editar datos) en la Fase 2, sin reescribir la arquitectura

### Ejemplos de preguntas que debe poder responder

```
# Pedidos y Clientes
"¿Cuántos pedidos están pendientes hoy?"
"¿Qué pedidos tiene Granja Los Pinos?"
"¿Cuáles son los despachos en tránsito?"
"¿Cuál es mi vendedor con más ventas este mes?"
"¿Hay algún pedido urgente por entregar?"
"Dame un resumen del estado del negocio"
"¿Cuánto ha comprado Avícola El Trigal en total?"
"¿Cuántos productos tenemos activos en el catálogo?"
"¿Cuál es el producto más vendido?"

# Competencia
"¿Qué productos de la competencia están más baratos que los nuestros?"

# Facturación
"¿Cuántos pedidos están sin facturar?"
"¿Cuál es el monto total pendiente de facturar?"
"¿Qué pedidos tienen facturación parcial?"
"¿Cuánto se ha facturado este mes?"

# Flotas
"¿Cuántos vehículos activos tenemos?"
"¿Qué viajes están programados para hoy?"
"¿Cuál es la utilización promedio de la flota?"
"¿Cuántos viajes se completaron esta semana?"
"¿Cuál es el costo total de fletes del mes?"

# Cuotas y Ventas
"¿Cómo va el cumplimiento de ventas este mes?"
"¿Cuál es la zona con mejor cumplimiento?"
"¿Qué vendedor tiene el mayor % de cumplimiento?"
"¿Cómo va la cuota del producto X?"
"¿Cuál es la tasa de cambio actual?"
"Compara el plan vs real por zona"
```

---

## ARQUITECTURA DE LA SOLUCIÓN

### Patrón: Context Injection con backend intercambiable

```
Usuario escribe pregunta
        ↓
ask_view (Django POST)
        ↓
1. Guardar pregunta en BD (ChatMensaje, rol='user')
2. Cargar historial reciente (últimos 10 mensajes)
3. build_context_for_org(org) → resumen BD en texto
4. LLMBackend.ask(pregunta, historial, contexto) → respuesta
5. Guardar respuesta en BD (ChatMensaje, rol='assistant')
        ↓
Retornar partial HTMX con los 2 nuevos mensajes
```

### Diseño para escalar a Fase 2 (Function Calling)

La arquitectura debe separar en capas independientes:

```
views.py          → solo recibe request, llama servicios, retorna HTTP
services/context.py → construye el contexto de BD (lectura)
services/base.py  → interfaz abstracta del LLM
services/gemini.py → implementación concreta Gemini
```

En Fase 2, `services/context.py` evolucionará a `services/tools.py` con funciones que el LLM puede invocar. Las views no cambiarán.

---

## ESTRUCTURA DE ARCHIVOS A CREAR

```
apps/chat_ia/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── migrations/
│   └── __init__.py
└── services/
    ├── __init__.py
    ├── base.py
    ├── gemini.py
    └── context.py

templates/
├── chat_ia/
│   ├── chat.html
│   └── _mensaje.html
└── partials/
    └── chat_flotante.html
```

### Archivos existentes a modificar

```
config/settings/base.py    → INSTALLED_APPS + CHAT_IA_* settings
config/urls.py             → incluir chat_ia.urls
templates/base.html        → incluir chat_flotante.html
requirements.txt           → google-generativeai
.env                       → GEMINI_API_KEY
```

---

## ESPECIFICACIONES DETALLADAS

### 1. `apps/chat_ia/models.py`

```python
class ChatMensaje(TenantModel):
    """
    Mensaje del historial de conversación con la IA.
    Hereda `organization` de TenantModel.
    """
    ROL_CHOICES = [
        ('user',      'Usuario'),
        ('assistant', 'Asistente'),
    ]

    user      = ForeignKey(settings.AUTH_USER_MODEL,
                           on_delete=models.CASCADE,
                           related_name='chat_mensajes')
    rol       = CharField(max_length=10, choices=ROL_CHOICES)
    contenido = TextField()
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Mensaje de Chat IA'
        verbose_name_plural = 'Mensajes de Chat IA'
        ordering            = ['created_at']
        indexes = [
            models.Index(fields=['organization', 'user', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_rol_display()} — {self.created_at:%d/%m/%Y %H:%M}'
```

### 2. `apps/chat_ia/services/base.py`

```python
from abc import ABC, abstractmethod

class BaseLLMBackend(ABC):
    """
    Interfaz abstracta para backends de LLM.
    Implementar esta clase para añadir nuevos modelos (Claude, GPT, etc.)
    """

    @abstractmethod
    def ask(
        self,
        pregunta: str,
        historial: list[dict],   # [{'rol': 'user'|'assistant', 'contenido': str}]
        contexto: str,           # resumen de la BD en texto
        org_name: str,           # nombre de la organización
    ) -> str:
        """
        Envía la pregunta al LLM con contexto e historial.
        Retorna la respuesta como string.
        Lanza LLMError si falla la llamada.
        """
        ...


class LLMError(Exception):
    """Error al llamar al LLM (API key inválida, timeout, etc.)"""
    pass
```

### 3. `apps/chat_ia/services/gemini.py`

```python
SYSTEM_PROMPT_TEMPLATE = """
Eres el asistente inteligente de gestión de {org_name}.

Tienes acceso a los datos actuales del sistema de pedidos, \
despachos, clientes, productos, competencia, facturación, \
flotas de transporte y cuotas/ventas de la empresa.

REGLAS ESTRICTAS:
- Responde SIEMPRE en español
- Sé conciso y directo — máximo 3-4 párrafos por respuesta
- Para montos de dinero usa $ y dos decimales (ej: $1,250.00)
- Para fechas usa formato DD/MM/YYYY
- Si no tienes la información exacta en los datos, dilo \
  claramente: "No tengo ese dato en el sistema"
- No inventes pedidos, clientes ni montos que no estén en el contexto
- Si te preguntan algo ajeno al negocio (política, chistes, etc.), \
  responde amablemente que eres un asistente especializado en la \
  gestión de {org_name}
- Cuando listes pedidos o clientes, usa formato de lista clara
- Puedes hacer cálculos simples: sumas, promedios, comparaciones
- Para consultas de cuotas/ventas, incluye siempre el % de cumplimiento
- Para consultas de flotas, incluye el % de utilización del vehículo

DATOS ACTUALES DEL SISTEMA (actualizados en tiempo real):
{context}
"""

class GeminiBackend(BaseLLMBackend):
    MODEL_NAME = 'gemini-2.0-flash'

    def __init__(self):
        import google.generativeai as genai
        from django.conf import settings
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise LLMError(
                'GEMINI_API_KEY no está configurada en las variables de entorno.'
            )
        genai.configure(api_key=api_key)
        self._genai = genai

    def ask(self, pregunta, historial, contexto, org_name):
        try:
            model = self._genai.GenerativeModel(
                model_name=self.MODEL_NAME,
                system_instruction=SYSTEM_PROMPT_TEMPLATE.format(
                    org_name=org_name,
                    context=contexto,
                ),
            )
            # Convertir historial al formato de Gemini
            chat_history = [
                {
                    'role': 'user' if m['rol'] == 'user' else 'model',
                    'parts': [m['contenido']],
                }
                for m in historial
            ]
            chat = model.start_chat(history=chat_history)
            response = chat.send_message(pregunta)
            return response.text
        except Exception as e:
            raise LLMError(f'Error al llamar a Gemini: {e}') from e
```

### 4. `apps/chat_ia/services/context.py`

La función principal debe construir un texto estructurado con los datos de la organización. **Usa `.values()` y agregaciones — nunca cargues objetos completos en memoria.**

**IMPORTANTE:** Si `org` es `None` (superadmin sin organización), retorna un mensaje indicando que debe seleccionar una organización desde el admin panel.

**Modelos a importar para construir contexto:**
```python
from apps.pedidos.models import Pedido, PedidoItem, Cliente, Factura
from apps.productos.models import Producto
from apps.competencia.models import CompetenciaRegistro
from apps.flotas.models import Vehiculo, Viaje, ViajeDetalle
from apps.cuotas.models import VentaMensual, TasaCambio
```

**Queries de facturación:**
```python
# Pedidos sin facturar (total > 0, sin facturas asociadas)
from django.db.models import Sum, Count, Q, F, Subquery, OuterRef
pedidos_org = Pedido.objects.filter(organization=org).exclude(estado='Cancelado')
sin_facturar = pedidos_org.annotate(
    total_facturado=Sum('facturas__monto')
).filter(Q(total_facturado__isnull=True) | Q(total_facturado=0), total__gt=0)

# Monto facturado del mes
from django.utils import timezone
mes_actual = timezone.now().replace(day=1).date()
facturado_mes = Factura.objects.filter(
    pedido__organization=org,
    fecha_factura__gte=mes_actual,
).aggregate(total=Sum('monto'))['total'] or 0
```

**Queries de flotas:**
```python
vehiculos_activos = Vehiculo.objects.filter(organization=org, is_active=True)
viajes_mes = Viaje.objects.filter(organization=org, fecha__gte=mes_actual)
viajes_programados = viajes_mes.filter(estado='Programado').count()
viajes_en_ruta = viajes_mes.filter(estado='En Ruta').count()
costo_fletes_mes = viajes_mes.filter(estado='Completado').aggregate(
    total=Sum('costo_flete'))['total'] or 0
```

**Queries de cuotas:**
```python
# Último periodo con datos
ultimo_periodo = VentaMensual.objects.filter(
    organization=org
).order_by('-periodo').values_list('periodo', flat=True).first()

if ultimo_periodo:
    ventas_periodo = VentaMensual.objects.filter(
        organization=org, periodo=ultimo_periodo)
    # Cumplimiento global
    totales = ventas_periodo.aggregate(
        plan=Sum('plan_venta_usd'), real=Sum('real_venta_usd'))
    # Por zona
    por_zona = ventas_periodo.values('zona_nombre').annotate(
        plan=Sum('plan_venta_usd'), real=Sum('real_venta_usd'))
    # Por vendedor (top 5)
    por_vendedor = ventas_periodo.values('vendedor_nombre').annotate(
        plan=Sum('plan_venta_usd'), real=Sum('real_venta_usd')
    ).order_by('-real')[:5]

# Tasa de cambio más reciente
tasa = TasaCambio.objects.filter(organization=org).first()  # ya ordenado por -fecha
```

El contexto debe incluir estas secciones:

**Sección 1 — Resumen ejecutivo** (siempre presente)
```
=== RESUMEN EJECUTIVO ===
Fecha y hora actual: DD/MM/YYYY HH:MM
Total pedidos (todos): N
  - Pendientes: N
  - Confirmados: N
  - En Proceso: N
  - Entregados: N
  - Cancelados: N
Total clientes: N
Total productos activos: N
Despachos pendientes (sin despachar): N
Despachos en tránsito: N
Ventas del mes actual (no cancelados): $XX,XXX.XX

--- Facturación ---
Pedidos sin facturar: N (monto total: $XX,XXX.XX)
Pedidos con facturación parcial: N
Pedidos totalmente facturados: N
Monto total facturado (mes actual): $XX,XXX.XX
Monto pendiente de facturar (mes actual): $XX,XXX.XX

--- Flotas ---
Vehículos activos: N
Viajes programados: N
Viajes en ruta: N
Viajes completados (mes actual): N
Costo total fletes (mes actual): $XX,XXX.XX
Utilización promedio (%): XX.X%

--- Cuotas y Ventas ---
Periodos con datos: YYYY-MM, YYYY-MM, ...
Cumplimiento global de ventas (último periodo): XX.X%
Tasa de cambio más reciente: XX.XXXX Bs/USD (fuente, fecha)
```

**Sección 2 — Pedidos recientes** (últimos 20, desc)
```
=== ÚLTIMOS 20 PEDIDOS ===
- PED-0045 | Cliente: Granja Los Pinos | Vendedor: Carlos M. |
  Estado: Confirmado | Despacho: Programado |
  Fecha pedido: 18/03/2026 | Entrega estimada: 22/03/2026 |
  Total: $3,200.00
...
```

**Sección 3 — Top clientes** (top 10 por compras totales, no cancelados)
```
=== TOP 10 CLIENTES POR COMPRAS ===
1. Avícola El Trigal C.A. — 12 pedidos — Total: $45,200.00
2. Granja Los Pinos — 8 pedidos — Total: $28,500.00
...
```

**Sección 4 — Top productos** (top 10 más vendidos por cantidad)
```
=== TOP 10 PRODUCTOS MÁS VENDIDOS ===
1. Alimento Iniciador Premium — 150 unidades — $12,000.00
2. Vitaminas Avícolas Plus — 95 unidades — $4,750.00
...
```

**Sección 5 — Competencia reciente** (últimos 10 registros)
```
=== INTELIGENCIA DE COMPETENCIA (últimos 10) ===
- 15/03/2026 | Producto: Pollo Iniciador ALIPA |
  Competidor: Agro Barinas | Su precio: $21.00 | Nuestro: $24.00 |
  Diferencia: +$3.00 (somos más caros)
...
```

**Sección 6 — Alertas activas**
```
=== ALERTAS ACTIVAS ===
⚠ Pedidos vencidos (fecha entrega pasada, no entregados): N
  - PED-0038 | Avícola El Trigal | Vencido: 15/03/2026 | Total: $1,800.00

⚠ Pedidos sin mover en despacho (>3 días en "Pendiente Despacho"):
  - PED-0041 | Granja Los Pinos | Sin mover desde: 14/03/2026

⚠ Pedidos con alto monto sin facturar (>$5,000, estado != Cancelado):
  - PED-0035 | Total: $8,500.00 | Facturado: $0.00

⚠ Viajes con sobrecarga (>100% capacidad):
  - Viaje 20/03/2026 | Vehículo ABC-123 | Utilización: 115%
```

**Sección 7 — Facturación reciente** (últimas 10 facturas)
```
=== ÚLTIMAS 10 FACTURAS ===
- FAC-0089 | Pedido: PED-0045 | Cliente: Granja Los Pinos |
  Fecha: 18/03/2026 | Monto: $3,200.00
...
```

**Sección 8 — Flotas** (viajes recientes y vehículos)
```
=== FLOTA DE VEHÍCULOS ===
- ABC-123 | Ford F-350 | Capacidad: 5,000 kg | Chofer: Carlos M. | Activo
- DEF-456 | Toyota Hilux | Capacidad: 2,500 kg | Sin chofer | Activo
...

=== ÚLTIMOS 10 VIAJES ===
- 20/03/2026 | Vehículo: ABC-123 | Chofer: Carlos M. |
  Estado: En Ruta | Pedidos: 4 | Peso: 3,800 kg (76.0%) |
  Costo flete: $150.00
...
```

**Sección 9 — Cuotas y Ventas** (resumen del último periodo)
```
=== CUOTAS Y VENTAS — ÚLTIMO PERIODO (YYYY-MM) ===

Por Zona:
- Norte | Plan: $50,000 | Real: $42,000 | Cumplimiento: 84.0%
- Sur | Plan: $30,000 | Real: $31,500 | Cumplimiento: 105.0%
...

Top 5 Vendedores por cumplimiento:
1. Juan Pérez | Plan: $20,000 | Real: $22,000 | 110.0%
2. María López | Plan: $18,000 | Real: $15,300 | 85.0%
...

Top 5 Productos por venta real:
1. Producto A | Plan: 100 uds / $5,000 | Real: 95 uds / $4,750 | 95.0%
2. Producto B | Plan: 200 uds / $8,000 | Real: 190 uds / $7,600 | 95.0%
...
```

Si alguna sección no tiene datos, escribe: `[Sin datos]`

**Límite de tokens**: el contexto completo no debe superar ~6000 tokens (~24,000 caracteres). Trunca las listas si es necesario. Prioriza las secciones 1 (resumen), 6 (alertas) y 9 (cuotas) ya que son las más consultadas.

### 5. `apps/chat_ia/views.py`

```python
# ask_view: maneja el POST del chat (HTMX)
@login_required
@role_required('gerente', 'superadmin')
def ask_view(request):
    """
    Recibe una pregunta, consulta la IA y retorna los mensajes nuevos.
    Solo acepta POST. Diseñado para HTMX.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    pregunta = request.POST.get('pregunta', '').strip()

    # Validaciones
    if not pregunta:
        return JsonResponse({'error': 'La pregunta no puede estar vacía.'}, status=400)
    if len(pregunta) > 500:
        return JsonResponse({'error': 'Pregunta muy larga (máx 500 caracteres).'}, status=400)

    # Manejar superadmin sin org
    org = request.org
    if not org:
        # Superadmin: no puede usar chat sin org
        msg_error = ChatMensaje.objects.create(
            organization=None,  # No tiene org — manejar en modelo o usar org ficticia
            ...
        )
        # ALTERNATIVA: retornar mensaje de error directo sin guardar en BD
        if request.htmx:
            return HttpResponse(
                '<div class="text-center text-sm text-slate-500 py-4">'
                'El chat IA requiere una organización. '
                'Accede como gerente de una organización para usarlo.'
                '</div>'
            )
        return redirect('chat_ia:chat')

    # Rate limiting: máx 30 preguntas por hora por usuario
    hace_una_hora = timezone.now() - timedelta(hours=1)
    preguntas_recientes = ChatMensaje.objects.filter(
        organization=org,
        user=request.user,
        rol='user',
        created_at__gte=hace_una_hora,
    ).count()
    if preguntas_recientes >= 30:
        msg_error = ChatMensaje.objects.create(
            organization=org,
            user=request.user,
            rol='assistant',
            contenido='Has alcanzado el límite de 30 consultas por hora. '
                      'Por favor espera unos minutos antes de continuar.',
        )
        if request.htmx:
            return render(request, 'chat_ia/_mensaje.html',
                          {'mensajes': [msg_error]})
        return redirect('chat_ia:chat')

    # Guardar pregunta del usuario
    msg_user = ChatMensaje.objects.create(
        organization=org,
        user=request.user,
        rol='user',
        contenido=pregunta,
    )

    # Cargar historial (últimos N mensajes, excluyendo el que acabamos de crear)
    n = getattr(settings, 'CHAT_IA_HISTORY_LENGTH', 10)
    historial_qs = ChatMensaje.objects.filter(
        organization=org,
        user=request.user,
    ).exclude(pk=msg_user.pk).order_by('-created_at')[:n]
    historial = [
        {'rol': m.rol, 'contenido': m.contenido}
        for m in reversed(list(historial_qs))
    ]

    # Construir contexto y llamar al LLM
    try:
        from .services.context import build_context_for_org
        from .services.gemini import GeminiBackend
        contexto = build_context_for_org(org)
        backend = GeminiBackend()
        respuesta_texto = backend.ask(
            pregunta=pregunta,
            historial=historial,
            contexto=contexto,
            org_name=org.name,
        )
    except Exception as e:
        respuesta_texto = (
            'No pude procesar tu consulta en este momento. '
            'Verifica que la API key de Gemini esté configurada '
            'o intenta de nuevo en unos segundos.'
        )

    # Guardar respuesta de la IA
    msg_assistant = ChatMensaje.objects.create(
        organization=org,
        user=request.user,
        rol='assistant',
        contenido=respuesta_texto,
    )

    # Retornar los 2 mensajes nuevos como HTML parcial
    if request.htmx:
        return render(request, 'chat_ia/_mensaje.html', {
            'mensajes': [msg_user, msg_assistant],
        })

    return redirect('chat_ia:chat')


# chat_view: página completa del chat
@login_required
@role_required('gerente', 'superadmin')
def chat_view(request):
    """
    Página completa del historial de conversación.
    Accesible desde el sidebar o directamente por URL.
    """
    if not request.org:
        mensajes = ChatMensaje.objects.none()
    else:
        mensajes = ChatMensaje.objects.filter(
            organization=request.org,
            user=request.user,
        ).order_by('created_at')[:50]

    return render(request, 'chat_ia/chat.html', {'mensajes': mensajes})
```

### 6. `apps/chat_ia/urls.py`

```python
from django.urls import path
from . import views

app_name = 'chat_ia'

urlpatterns = [
    path('',     views.chat_view, name='chat'),
    path('ask/', views.ask_view,  name='ask'),
]
```

### 7. `templates/chat_ia/_mensaje.html`

Partial HTMX que renderiza uno o más mensajes:

```html
{% for mensaje in mensajes %}
<div class="flex {% if mensaje.rol == 'user' %}justify-end{% else %}justify-start{% endif %} mb-3">
  <div class="max-w-[80%] rounded-2xl px-4 py-3 text-sm
              {% if mensaje.rol == 'user' %}
                bg-gradient-to-r from-brand-blue to-brand-green text-white rounded-br-sm
              {% else %}
                surface-base text-slate-800 dark:text-slate-200 rounded-bl-sm
              {% endif %}">

    {% if mensaje.rol == 'assistant' %}
    <div class="flex items-center gap-1.5 mb-1.5">
      <div class="w-4 h-4 rounded-full bg-gradient-to-br from-brand-blue to-brand-green
                  flex items-center justify-center">
        <i class="fas fa-robot text-white" style="font-size: 8px;"></i>
      </div>
      <span class="text-xs font-semibold text-brand-blue dark:text-blue-400">
        Asistente IA
      </span>
    </div>
    {% endif %}

    <p class="whitespace-pre-wrap leading-relaxed">{{ mensaje.contenido }}</p>

    <p class="text-[10px] mt-1.5
              {% if mensaje.rol == 'user' %}text-white/60{% else %}text-slate-400{% endif %}">
      {{ mensaje.created_at|date:"H:i" }}
    </p>
  </div>
</div>
{% endfor %}
```

### 8. `templates/chat_ia/chat.html`

Página completa del historial. Extiende `base.html`:

```html
{% extends "base.html" %}
{% block title %}Chat IA — SmartSales{% endblock %}
{% block breadcrumb %}Asistente IA{% endblock %}

{% block content %}
<div class="p-6 max-w-3xl mx-auto flex flex-col h-[calc(100vh-4rem)]">

  <div class="flex items-center justify-between mb-4">
    <div>
      <h1 class="text-title">Asistente IA</h1>
      <p class="text-subtitle">{% if request.org %}{{ request.org.name }}{% endif %}</p>
    </div>
  </div>

  <!-- Historial -->
  <div id="chat-historial"
       class="flex-1 overflow-y-auto card-glass !p-4 mb-4 space-y-1">
    {% if mensajes %}
      {% for mensaje in mensajes %}
        {% include 'chat_ia/_mensaje.html' with mensajes=forloop.parentloop.counter|default:mensajes %}
      {% endfor %}
    {% else %}
    <div class="flex flex-col items-center justify-center h-full text-center">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-blue to-brand-green
                  flex items-center justify-center mb-4 shadow-lg">
        <i class="fas fa-robot text-white text-2xl"></i>
      </div>
      <p class="font-semibold text-slate-700 dark:text-slate-300">
        Soy tu asistente IA
      </p>
      <p class="text-subtitle text-sm mt-1 max-w-sm">
        Pregúntame sobre pedidos, clientes, productos, despachos o el estado del negocio.
      </p>
    </div>
    {% endif %}
  </div>

  <!-- Input -->
  <form hx-post="{% url 'chat_ia:ask' %}"
        hx-target="#chat-historial"
        hx-swap="beforeend"
        x-data="{ pregunta: '', cargando: false }"
        @htmx:before-request="cargando = true"
        @htmx:after-request="cargando = false; pregunta = ''; $nextTick(() => { const h = document.getElementById('chat-historial'); h.scrollTop = h.scrollHeight; })"
        class="flex gap-2">
    {% csrf_token %}
    <input type="text"
           name="pregunta"
           x-model="pregunta"
           :disabled="cargando"
           placeholder="Escribe tu consulta..."
           maxlength="500"
           autocomplete="off"
           class="flex-1 input-base !py-2.5">
    <button type="submit"
            :disabled="cargando || !pregunta.trim()"
            class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-brand-blue to-brand-green
                   text-white font-semibold text-sm
                   hover:opacity-90 transition-opacity disabled:opacity-40 flex-shrink-0">
      <i class="fas fa-paper-plane mr-1"></i> Enviar
    </button>
  </form>

</div>

<script>
  // Auto-scroll al último mensaje al cargar
  const hist = document.getElementById('chat-historial');
  if (hist) hist.scrollTop = hist.scrollHeight;

  // Auto-scroll cuando HTMX añade un mensaje
  document.body.addEventListener('htmx:afterSwap', function(e) {
    if (hist) hist.scrollTop = hist.scrollHeight;
  });
</script>
{% endblock %}
```

### 9. `templates/partials/chat_flotante.html`

Este es el componente más importante. Alpine.js gestiona el estado del panel.

```html
{# Botón flotante + panel de chat deslizante #}
{# Solo visible para can_access_dashboard #}

<div x-data="chatFlotante()"
     x-init="init()"
     class="fixed bottom-6 right-6 z-50">

  <!-- Panel de chat -->
  <div x-show="abierto"
       x-transition:enter="transition ease-out duration-300"
       x-transition:enter-start="opacity-0 translate-y-4 scale-95"
       x-transition:enter-end="opacity-100 translate-y-0 scale-100"
       x-transition:leave="transition ease-in duration-200"
       x-transition:leave-start="opacity-100 translate-y-0 scale-100"
       x-transition:leave-end="opacity-0 translate-y-4 scale-95"
       class="absolute bottom-16 right-0 w-[380px] h-[560px]
              surface-base rounded-2xl shadow-2xl flex flex-col overflow-hidden
              border border-slate-200 dark:border-white/10"
       style="display: none;">

    <!-- Header del panel -->
    <div class="h-14 bg-gradient-to-r from-brand-blue to-brand-green
                flex items-center justify-between px-4 flex-shrink-0">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center">
          <i class="fas fa-robot text-white text-sm"></i>
        </div>
        <div>
          <p class="text-white font-semibold text-sm leading-tight">Asistente IA</p>
          <p class="text-white/70 text-[10px] leading-tight">
            {% if request.org %}{{ request.org.name }}{% endif %}
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <a href="{% url 'chat_ia:chat' %}"
           class="text-white/70 hover:text-white transition-colors"
           title="Abrir en página completa">
          <i class="fas fa-expand-alt text-xs"></i>
        </a>
        <button @click="cerrar()"
                class="text-white/70 hover:text-white transition-colors">
          <i class="fas fa-times"></i>
        </button>
      </div>
    </div>

    <!-- Historial de mensajes -->
    <div id="chat-flotante-historial"
         class="flex-1 overflow-y-auto p-3 space-y-1 bg-slate-50 dark:bg-slate-900/30">

      <!-- Mensaje de bienvenida (solo si no hay historial) -->
      <template x-if="!hayMensajes">
        <div class="flex flex-col items-center justify-center h-full text-center py-8">
          <i class="fas fa-comments text-3xl text-slate-300 dark:text-slate-600 mb-3"></i>
          <p class="text-sm font-medium text-slate-600 dark:text-slate-400">
            ¿En qué puedo ayudarte?
          </p>
          <!-- Sugerencias rápidas -->
          <div class="mt-4 space-y-2 w-full px-2">
            <template x-for="sug in sugerencias">
              <button @click="enviarSugerencia(sug)"
                      class="w-full text-left text-xs px-3 py-2 rounded-xl
                             bg-white dark:bg-slate-800 border border-slate-200
                             dark:border-white/10 text-slate-600 dark:text-slate-400
                             hover:border-brand-blue hover:text-brand-blue transition-all">
                <i class="fas fa-chevron-right text-[9px] mr-1 opacity-50"></i>
                <span x-text="sug"></span>
              </button>
            </template>
          </div>
        </div>
      </template>

      <!-- Mensajes del historial (cargados con HTMX al abrir) -->
      <div id="chat-flotante-mensajes"
           hx-get="{% url 'chat_ia:chat' %}?formato=flotante"
           hx-trigger="load"
           hx-swap="innerHTML">
      </div>

      <!-- Indicador "escribiendo..." -->
      <div x-show="cargando" class="flex justify-start mb-3">
        <div class="surface-base rounded-2xl rounded-bl-sm px-4 py-3">
          <div class="flex gap-1 items-center">
            <div class="w-1.5 h-1.5 rounded-full bg-brand-blue animate-bounce" style="animation-delay: 0ms"></div>
            <div class="w-1.5 h-1.5 rounded-full bg-brand-blue animate-bounce" style="animation-delay: 150ms"></div>
            <div class="w-1.5 h-1.5 rounded-full bg-brand-blue animate-bounce" style="animation-delay: 300ms"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="p-3 border-t border-slate-200 dark:border-white/5 flex-shrink-0">
      <form hx-post="{% url 'chat_ia:ask' %}"
            hx-target="#chat-flotante-mensajes"
            hx-swap="beforeend"
            hx-on::before-request="cargando = true; hayMensajes = true"
            hx-on::after-request="cargando = false; scrollAbajo(); limpiarInput()"
            class="flex gap-2"
            x-ref="formChat">
        {% csrf_token %}
        <input type="text"
               name="pregunta"
               x-ref="inputChat"
               x-model="pregunta"
               @keydown.enter.prevent="if(pregunta.trim()) $refs.formChat.requestSubmit()"
               :disabled="cargando"
               placeholder="Escribe tu consulta..."
               maxlength="500"
               autocomplete="off"
               class="flex-1 input-base !py-2 !text-xs">
        <button type="submit"
                :disabled="cargando || !pregunta.trim()"
                data-no-disable="true"
                class="w-9 h-9 rounded-xl bg-gradient-to-r from-brand-blue to-brand-green
                       text-white flex items-center justify-center
                       hover:opacity-90 transition-opacity disabled:opacity-40 flex-shrink-0">
          <i class="fas fa-paper-plane text-xs"></i>
        </button>
      </form>
    </div>
  </div>

  <!-- Botón flotante -->
  <button @click="toggle()"
          class="w-14 h-14 rounded-full bg-gradient-to-br from-brand-blue to-brand-green
                 text-white shadow-lg shadow-brand-blue/30
                 hover:shadow-xl hover:shadow-brand-blue/40 hover:scale-105
                 transition-all flex items-center justify-center relative">
    <i class="fas fa-robot text-xl" x-show="!abierto"></i>
    <i class="fas fa-times text-xl" x-show="abierto"></i>
  </button>

</div>

<script>
function chatFlotante() {
  return {
    abierto: false,
    cargando: false,
    hayMensajes: false,
    pregunta: '',
    sugerencias: [
      '¿Cuántos pedidos están pendientes?',
      'Dame un resumen del negocio',
      '¿Cómo va el cumplimiento de ventas?',
      '¿Cuánto falta por facturar?',
      '¿Qué viajes hay programados hoy?',
    ],

    init() {
      this.abierto = localStorage.getItem('chat_ia_abierto') === 'true';
    },

    toggle() {
      this.abierto = !this.abierto;
      localStorage.setItem('chat_ia_abierto', this.abierto);
      if (this.abierto) {
        this.$nextTick(() => {
          this.scrollAbajo();
          this.$refs.inputChat?.focus();
        });
      }
    },

    cerrar() {
      this.abierto = false;
      localStorage.setItem('chat_ia_abierto', 'false');
    },

    scrollAbajo() {
      const hist = document.getElementById('chat-flotante-historial');
      if (hist) hist.scrollTop = hist.scrollHeight;
    },

    limpiarInput() {
      this.pregunta = '';
      this.$nextTick(() => this.$refs.inputChat?.focus());
    },

    enviarSugerencia(texto) {
      this.pregunta = texto;
      this.$nextTick(() => this.$refs.formChat?.requestSubmit());
    },
  }
}
</script>
```

**Nota importante sobre `data-no-disable="true"`:** El `base.html` tiene un listener global que deshabilita botones submit al enviar formularios. El botón del chat flotante usa `data-no-disable` para evitar conflicto (verificar que el listener en base.html respete este atributo — si usa `btn.dataset.noDisable`, ya es compatible).

---

## INTEGRACIONES EN ARCHIVOS EXISTENTES

### `config/settings/base.py` — añadir al final

```python
# ── Chat IA ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY          = env('GEMINI_API_KEY', default='')
CHAT_IA_BACKEND         = 'apps.chat_ia.services.gemini.GeminiBackend'
CHAT_IA_HISTORY_LENGTH  = 10    # mensajes de historial incluidos en cada prompt
CHAT_IA_RATE_LIMIT_HOUR = 30    # máximo de preguntas por usuario por hora
```

### `config/settings/base.py` — INSTALLED_APPS

```python
LOCAL_APPS = [
    'apps.accounts',
    'apps.pedidos',
    'apps.despacho',
    'apps.competencia',
    'apps.campo',
    'apps.reportes',
    'apps.productos',
    'apps.chat_ia',    # ← añadir aquí
]
```

### `config/urls.py` — añadir

```python
path('chat-ia/', include('apps.chat_ia.urls', namespace='chat_ia')),
```

### `templates/base.html` — dentro del layout con sidebar

Busca antes de `</body>` (pero después de la modal de confirmación) y añade:

```html
{# Chat IA flotante — solo para gerentes y superadmins #}
{% if user.is_authenticated and user.can_access_dashboard %}
  {% include 'partials/chat_flotante.html' %}
{% endif %}
```

### `requirements.txt` — añadir

```
google-generativeai==0.8.3
```

### `.env` — añadir

```bash
# ── Chat IA (Google AI Studio — gratis) ─────────────────────────────────────
# Obtener en: https://aistudio.google.com → Get API key
GEMINI_API_KEY=
```

---

## TESTS A ESCRIBIR

Crear `tests/test_chat_ia.py`:

```python
"""
Tests del módulo Chat IA.
"""
import pytest
from django.urls import reverse
from apps.chat_ia.models import ChatMensaje
from .conftest import OrganizationFactory


@pytest.mark.django_db
class TestChatMensaje:

    def test_mensaje_guardado_con_org_correcta(self, org, gerente):
        msg = ChatMensaje.objects.create(
            organization=org,
            user=gerente,
            rol='user',
            contenido='¿Cuántos pedidos hay?',
        )
        assert msg.organization == org
        assert msg.rol == 'user'

    def test_historial_filtrado_por_org(self, org, gerente):
        otra_org = OrganizationFactory()
        ChatMensaje.objects.create(organization=org, user=gerente,
                                   rol='user', contenido='Mensaje org A')
        ChatMensaje.objects.create(organization=otra_org, user=gerente,
                                   rol='user', contenido='Mensaje org B')
        mensajes_org = ChatMensaje.objects.filter(organization=org)
        assert mensajes_org.count() == 1
        assert mensajes_org.first().contenido == 'Mensaje org A'


@pytest.mark.django_db
class TestContextBuilder:

    def test_context_incluye_datos_de_la_org(self, org, gerente, cliente, pedido):
        from apps.chat_ia.services.context import build_context_for_org
        context = build_context_for_org(org)
        assert 'RESUMEN EJECUTIVO' in context
        assert 'ÚLTIMOS' in context

    def test_context_no_incluye_datos_de_otra_org(self, org, gerente):
        from apps.chat_ia.services.context import build_context_for_org
        from .conftest import OrganizationFactory, PedidoFactory, ClienteFactory
        otra_org = OrganizationFactory()
        cliente_otro = ClienteFactory(organization=otra_org)
        PedidoFactory(organization=otra_org, cliente=cliente_otro,
                      vendedor=gerente, numero='PED-9999')
        context = build_context_for_org(org)
        assert 'PED-9999' not in context

    def test_context_maneja_org_sin_datos(self, org):
        from apps.chat_ia.services.context import build_context_for_org
        context = build_context_for_org(org)
        assert isinstance(context, str)
        assert len(context) > 0

    def test_context_maneja_org_none(self):
        from apps.chat_ia.services.context import build_context_for_org
        context = build_context_for_org(None)
        assert isinstance(context, str)

    def test_context_incluye_facturacion(self, org, gerente, cliente, pedido):
        from apps.chat_ia.services.context import build_context_for_org
        from apps.pedidos.models import Factura
        Factura.objects.create(
            pedido=pedido, numero_factura='FAC-001',
            fecha_factura='2026-03-01', monto=500, created_by=gerente)
        context = build_context_for_org(org)
        assert 'Facturación' in context or 'factur' in context.lower()

    def test_context_incluye_flotas(self, org, gerente):
        from apps.chat_ia.services.context import build_context_for_org
        from .conftest import VehiculoFactory
        VehiculoFactory(organization=org)
        context = build_context_for_org(org)
        assert 'Flotas' in context or 'Vehículo' in context or 'vehículo' in context.lower()

    def test_context_incluye_cuotas(self, org):
        from apps.chat_ia.services.context import build_context_for_org
        from .conftest import VentaMensualFactory
        VentaMensualFactory(organization=org)
        context = build_context_for_org(org)
        assert 'Cuotas' in context or 'CUOTAS' in context or 'cumplimiento' in context.lower()


@pytest.mark.django_db
class TestAskView:

    def test_vendedor_no_tiene_acceso(self, client_vendedor):
        resp = client_vendedor.post(reverse('chat_ia:ask'),
                                   {'pregunta': 'Hola'})
        assert resp.status_code in (302, 403)

    def test_pregunta_vacia_retorna_400(self, client_gerente):
        resp = client_gerente.post(reverse('chat_ia:ask'),
                                  {'pregunta': '   '})
        assert resp.status_code == 400

    def test_pregunta_muy_larga_retorna_400(self, client_gerente):
        resp = client_gerente.post(reverse('chat_ia:ask'),
                                  {'pregunta': 'x' * 501})
        assert resp.status_code == 400

    def test_pregunta_guarda_mensaje_usuario_en_bd(
            self, client_gerente, org, gerente, monkeypatch):
        # Mockear el LLM para no llamar a la API real en tests
        from apps.chat_ia.services import gemini
        monkeypatch.setattr(
            gemini.GeminiBackend, 'ask',
            lambda self, **kw: 'Respuesta de prueba'
        )
        resp = client_gerente.post(
            reverse('chat_ia:ask'),
            {'pregunta': '¿Cuántos pedidos hay?'},
            HTTP_HX_REQUEST='true',
        )
        assert resp.status_code == 200
        assert ChatMensaje.objects.filter(
            organization=org, user=gerente, rol='user'
        ).exists()

    def test_rate_limit_bloquea_exceso(self, client_gerente, org, gerente):
        # Crear 30 mensajes recientes del usuario
        for _ in range(30):
            ChatMensaje.objects.create(
                organization=org, user=gerente,
                rol='user', contenido='Pregunta',
            )
        resp = client_gerente.post(
            reverse('chat_ia:ask'),
            {'pregunta': 'Una más'},
            HTTP_HX_REQUEST='true',
        )
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'límite' in content.lower()
```

---

## ORDEN DE IMPLEMENTACIÓN

Implementa exactamente en este orden. Después de cada paso, confirma los archivos creados antes de continuar:

```
Paso 1 — Scaffolding del módulo
  ├── apps/chat_ia/__init__.py
  ├── apps/chat_ia/apps.py
  └── apps/chat_ia/migrations/__init__.py

Paso 2 — Modelo + migración
  ├── apps/chat_ia/models.py    (ChatMensaje)
  └── Ejecutar: python manage.py makemigrations chat_ia

Paso 3 — Servicios de contexto
  ├── apps/chat_ia/services/__init__.py
  └── apps/chat_ia/services/context.py    (build_context_for_org)

Paso 4 — Backend LLM
  ├── apps/chat_ia/services/base.py    (BaseLLMBackend, LLMError)
  └── apps/chat_ia/services/gemini.py  (GeminiBackend)

Paso 5 — Views + URLs
  ├── apps/chat_ia/views.py    (ask_view, chat_view)
  └── apps/chat_ia/urls.py

Paso 6 — Templates del chat
  ├── templates/chat_ia/_mensaje.html
  └── templates/chat_ia/chat.html

Paso 7 — Componente flotante
  └── templates/partials/chat_flotante.html

Paso 8 — Integraciones en archivos existentes
  ├── config/settings/base.py    (INSTALLED_APPS + settings de Chat IA)
  ├── config/urls.py             (incluir chat_ia.urls)
  ├── templates/base.html        (incluir chat_flotante.html)
  ├── requirements.txt           (google-generativeai)
  └── .env                       (GEMINI_API_KEY)

Paso 9 — Tests
  └── tests/test_chat_ia.py

Paso 10 — Verificación final
  └── python manage.py migrate
  └── python manage.py runserver (verificar que no hay errores de import)
  └── pytest tests/ (verificar todos los tests pasan)
```

---

## PREGUNTAS DE CONFIRMACIÓN — RESPONDE ANTES DE CODIFICAR

Antes de escribir una sola línea de código, responde estas preguntas:

**1. Multi-tenancy:**
Explica en una oración cómo garantizarás que `build_context_for_org` nunca exponga datos de otra organización.

**2. Superadmin:**
¿Qué pasa cuando un superadmin (request.org = None) intenta usar el chat? Describe el flujo.

**3. Modelo:**
Muéstrame el modelo `ChatMensaje` completo con todos los campos, Meta, y por qué hereda de `TenantModel` y no directamente de `models.Model`.

**4. Graceful degradation:**
¿Qué pasa exactamente en `ask_view` si `GEMINI_API_KEY` está vacía? Describe el flujo paso a paso.

**5. HTMX:**
¿Cuál es el `hx-target` del formulario en `chat_flotante.html` y qué `hx-swap` usarás para añadir mensajes sin reemplazar los anteriores?

**6. Convenciones:**
Nombra 3 convenciones del proyecto (de `CLAUDE.md`) que aplicarás en este módulo.

**Solo después de que yo apruebe tus respuestas, comienza la implementación desde el Paso 1.**
