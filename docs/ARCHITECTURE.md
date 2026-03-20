# SmartSales Django — Arquitectura del Sistema

**Stack:** Django 5.2 + PostgreSQL 16 + HTMX + Alpine.js v3 + Tailwind CSS
**Deploy:** Docker + Nginx + DigitalOcean Droplet $6/mes

---

## Diagrama de alto nivel

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENTE (Browser)                             │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │   Dashboard      │  │  Formulario  │  │  Panel SuperAdmin │ │
│  │   Gerencial      │  │   Móvil      │  │  /admin-panel/    │ │
│  │  HTMX + Alpine   │  │  Alpine.js   │  │  Django Admin +   │ │
│  └──────────────────┘  └──────────────┘  │  Vistas custom    │ │
│                                          └───────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS (Nginx → Gunicorn)
┌───────────────────────────▼─────────────────────────────────────┐
│                     NGINX (proxy reverso)                        │
│  ┌─────────────────┐   ┌──────────────────────────────────────┐ │
│  │ Static files    │   │    /static/ y /media/ directos       │ │
│  │ /static/ media/ │   │    Todo lo demás → Gunicorn :8000    │ │
│  └─────────────────┘   └──────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│               DJANGO 5.2 + GUNICORN (3 workers)                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Middleware stack:                                        │   │
│  │  SecurityMiddleware → SessionMiddleware →                 │   │
│  │  AuthenticationMiddleware → TenantMiddleware             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐ │
│  │accounts/ │ │pedidos/  │ │despacho/ │ │competencia/ campo/ │ │
│  │ User     │ │ Pedido   │ │ (views   │ │ CompetReg  Móvil   │ │
│  │ Org      │ │ Item     │ │ only)    │ │                    │ │
│  │ Auth     │ │ Cliente  │ │          │ │                    │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                   PostgreSQL 16                                   │
│                                                                 │
│  organizations  users  clientes  pedidos  pedido_items          │
│  competencia_registros                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Modelo de datos

### `organizations`
```python
class Organization(models.Model):
    name       = CharField(max_length=200)
    slug       = SlugField(unique=True)
    is_active  = BooleanField(default=True)
    plan       = CharField(choices=['starter','pro','enterprise'])
    created_at = DateTimeField(auto_now_add=True)
```

### `users` (custom AbstractUser)
```python
class User(AbstractUser):
    organization = ForeignKey(Organization, null=True, blank=True)
    role         = CharField(choices=['superadmin','gerente','vendedor'])
    # username, email, password → heredados de AbstractUser
```

### `clientes`
```python
class Cliente(TenantModel):  # hereda organization FK
    nombre    = CharField(max_length=200)
    contacto  = CharField(blank=True)
    telefono  = CharField(blank=True)
    email     = EmailField(blank=True)
    direccion = TextField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

### `pedidos`
```python
class Pedido(TenantModel):
    ESTADOS = ['Pendiente','Confirmado','En Proceso','Entregado','Cancelado']
    ESTADOS_DESPACHO = ['Pendiente Despacho','Programado','En Tránsito','Despachado','Devuelto']

    numero         = CharField(max_length=20)          # PED-0001
    fecha_pedido   = DateField()
    fecha_entrega  = DateField(null=True, blank=True)
    cliente        = ForeignKey(Cliente)
    vendedor       = ForeignKey(User)
    estado         = CharField(choices=ESTADOS, default='Pendiente')
    estado_despacho= CharField(choices=ESTADOS_DESPACHO, default='Pendiente Despacho')
    ref_competencia= CharField(blank=True)
    observaciones  = TextField(blank=True)
    total          = DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by     = ForeignKey(User, related_name='pedidos_creados')
    created_at     = DateTimeField(auto_now_add=True)
    updated_at     = DateTimeField(auto_now=True)
```

### `pedido_items`
```python
class PedidoItem(models.Model):
    pedido   = ForeignKey(Pedido, related_name='items', on_delete=CASCADE)
    producto = CharField(max_length=200)
    sku      = CharField(max_length=50, blank=True)
    cantidad = DecimalField(max_digits=10, decimal_places=2)
    precio   = DecimalField(max_digits=12, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio
```

### `competencia_registros`
```python
class CompetenciaRegistro(TenantModel):
    fecha          = DateField()
    cliente        = ForeignKey(Cliente, null=True, blank=True)
    vendedor       = ForeignKey(User)
    producto       = CharField(max_length=200)
    competidor     = CharField(max_length=200)
    precio_comp    = DecimalField(null=True, blank=True)
    precio_nuestro = DecimalField(null=True, blank=True)
    accion_tomada  = TextField(blank=True)
    created_at     = DateTimeField(auto_now_add=True)
```

---

## Multi-tenancy en Django

**Estrategia:** `organization_id` en todos los modelos + middleware que inyecta `request.org`.

```
Request HTTP
    │
    ▼
TenantMiddleware
    ├─ Lee user.organization → request.org
    ├─ Si org inactiva → redirect 'cuenta_suspendida'
    └─ Si superadmin → request.org = None (acceso global)
    │
    ▼
View
    ├─ get_tenant_queryset(request) → Pedido.objects.filter(organization=request.org)
    └─ get_object_or_404 siempre incluye organization=request.org
```

**Clase base para modelos con tenant:**
```python
class TenantModel(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.PROTECT
    )

    class Meta:
        abstract = True
```

**Manager con filtro automático:**
```python
class TenantManager(models.Manager):
    def for_org(self, organization):
        return self.get_queryset().filter(organization=organization)
```

---

## Flujo de autenticación

```
1. GET /login/
2. POST /login/ → Django auth.authenticate(email, password)
3. Si org.is_active = False → error "cuenta suspendida"
4. auth.login(request, user)
5. Redirect según rol:
   - superadmin → /admin-panel/
   - gerente    → /dashboard/
   - vendedor   → /campo/
6. TenantMiddleware en cada request posterior verifica org activa
7. GET /logout/ → auth.logout → redirect /login/
```

---

## Patrón HTMX (actualizaciones parciales)

```
Usuario hace clic en "Cambiar estado" de un pedido
    │
    ▼
hx-post="/pedidos/{id}/cambiar-estado/"
hx-target="#fila-pedido-{id}"
hx-swap="outerHTML"
    │
    ▼
Django view cambiar_estado_pedido()
    ├─ Valida datos y permisos
    ├─ Actualiza estado en BD
    └─ if request.htmx:
           return render(request, 'partials/fila_pedido.html', {'pedido': p})
       return redirect('pedidos:lista')
    │
    ▼
HTMX reemplaza solo la fila en la tabla (sin recargar página)
```

---

## Patrón Alpine.js (interactividad cliente)

```
Modal de nuevo pedido:
    <div x-data="pedidoForm()">
        <button @click="open = true">Nuevo Pedido</button>
        <div x-show="open" x-transition>
            <form @submit.prevent="guardar()">
                <!-- items dinámicos -->
                <template x-for="item in items">...</template>
                <button @click="agregarItem()">+ Ítem</button>
            </form>
        </div>
    </div>

    <script>
    function pedidoForm() {
        return {
            open: false,
            items: [{ producto: '', cantidad: 1, precio: 0 }],
            total() { return this.items.reduce((s, i) => s + i.cantidad * i.precio, 0) },
            agregarItem() { this.items.push({ producto: '', cantidad: 1, precio: 0 }) },
        }
    }
    </script>
```

---

## Estructura de URLs

```
/                           → redirect /dashboard/ o /campo/
/login/                     → LoginView
/logout/                    → LogoutView

/dashboard/                 → DashboardView (gerente)
/pedidos/                   → PedidoListView
/pedidos/nuevo/             → PedidoCreateView
/pedidos/{id}/              → PedidoDetailView
/pedidos/{id}/editar/       → PedidoUpdateView
/pedidos/{id}/eliminar/     → PedidoDeleteView
/pedidos/{id}/estado/       → cambiar_estado (HTMX)
/despacho/                  → DespachoView (gerente)
/despacho/{id}/estado/      → cambiar_estado_despacho (HTMX)
/clientes/                  → ClienteListView
/clientes/nuevo/            → ClienteCreateView
/competencia/               → CompetenciaListView
/competencia/nuevo/         → CompetenciaCreateView
/reportes/vendedores/       → ReporteVendedoresView
/reportes/clientes/         → ReporteClientesView
/campo/                     → CampoView (vendedor)
/campo/pedido/nuevo/        → CampoPedidoCreateView
/campo/competencia/nuevo/   → CampoCompetenciaCreateView

/admin-panel/               → AdminPanelView (superadmin)
/admin-panel/orgs/          → OrgListView
/admin-panel/orgs/nueva/    → OrgCreateView
/admin-panel/orgs/{id}/     → OrgDetailView
/admin-panel/orgs/{id}/usuarios/ → OrgUsuariosView
```

---

## Deploy en DigitalOcean

**Infraestructura:**
```
DigitalOcean Droplet $6/mes
├── Ubuntu 24.04 LTS
├── Docker + Docker Compose
└── 3 contenedores:
    ├── web (Django + Gunicorn)
    ├── db  (PostgreSQL 16)
    └── nginx (proxy + SSL)
```

**Proceso de deploy:**
1. `git push origin main` (desde local)
2. SSH al servidor
3. `git pull`
4. `docker-compose build web`
5. `docker-compose up -d --force-recreate web`

Ver `docs/DEPLOY.md` para guía completa paso a paso.

---

## Seguridad

| Medida | Implementación |
|--------|---------------|
| CSRF | Django middleware (por defecto) |
| XSS | Django templates auto-escapan |
| SQL injection | ORM de Django (nunca raw SQL) |
| Auth | Django sessions + bcrypt |
| HTTPS | Nginx + Let's Encrypt |
| Headers de seguridad | Nginx + django.middleware.security |
| Aislamiento de tenant | TenantMiddleware + filtro en views |
| Validación de ownership | `get_object_or_404` con `organization=request.org` |
