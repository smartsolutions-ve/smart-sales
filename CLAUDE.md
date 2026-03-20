# CLAUDE.md — SmartSales Django

Instrucciones para Claude Code al trabajar en este proyecto.

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5.2 + Python 3.12 |
| Base de datos | PostgreSQL 16 |
| Frontend | Django Templates + HTMX + Alpine.js v3 + Tailwind CSS |
| Auth | Django Auth integrado (AbstractUser) |
| Deploy | Docker + Nginx + DigitalOcean Droplet $6/mes |
| Tests | pytest-django + factory_boy |
| Email | django-anymail + Resend |

## Estructura del proyecto

```
smartsales-django/
├── config/
│   ├── settings/
│   │   ├── base.py        # Settings compartidos
│   │   ├── dev.py         # DEBUG=True, SQLite opcional
│   │   └── prod.py        # DEBUG=False, PostgreSQL, seguridad
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/          # User, Organization, auth views
│   ├── pedidos/           # Pedido, PedidoItem, Cliente
│   ├── despacho/          # Vista de logística (usa modelos de pedidos)
│   ├── competencia/       # CompetenciaRegistro
│   ├── campo/             # Formulario móvil para vendedores
│   └── reportes/          # Vistas de analytics (vendedores, clientes)
├── templates/
│   ├── base.html          # Layout principal con HTMX + Alpine.js
│   ├── accounts/
│   ├── pedidos/
│   ├── despacho/
│   ├── competencia/
│   ├── campo/
│   ├── reportes/
│   └── partials/          # Fragmentos HTMX (tablas, filas, modales)
├── static/
│   ├── css/app.css        # Tailwind compilado
│   └── js/app.js          # Alpine.js stores globales
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Multi-tenancy

**NO usa RLS de PostgreSQL.** El aislamiento de datos se hace en la capa de aplicación:

1. `apps/accounts/middleware.py` → `TenantMiddleware`: inyecta `request.org` con la organización del usuario logueado
2. Todos los modelos tenant-specific heredan de `TenantModel` (abstract) que incluye `organization = ForeignKey(Organization)`
3. Cada view usa `get_queryset_for_org(request)` → filtra por `organization=request.org`
4. El superadmin (`role='superadmin'`) no tiene `organization` y accede a `/admin-panel/`

## Roles y permisos

| Rol | Acceso |
|-----|--------|
| `superadmin` | `/admin-panel/` — gestiona organizaciones y usuarios |
| `gerente` | Todo el dashboard (pedidos, despacho, reportes, competencia) |
| `vendedor` | Solo `/campo/` para registrar pedidos |

Decoradores disponibles:
- `@login_required` — cualquier usuario logueado
- `@role_required('gerente', 'admin')` — roles específicos
- `@superadmin_required` — solo superadmin

## Patrones HTMX

Respuestas parciales se retornan con el template de fragmento:
```python
# En la view, si es request HTMX retorna solo el fragmento
if request.htmx:
    return render(request, 'partials/tabla_pedidos.html', context)
return render(request, 'pedidos/lista.html', context)
```

**CSRF con HTMX:**
Todas las peticiones mutables (POST, PUT, DELETE) gestionadas por HTMX requieren token CSRF. En `templates/base.html` se configuró un event listener global (`htmx:configRequest`) que lee el token de las cookies y lo inyecta en el header `X-CSRFToken` automáticamente, evitando errores 403 Forbidden.

## Comandos de desarrollo

```bash
# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno (copiar y editar)
cp .env.example .env

# Crear base de datos y correr migraciones
python manage.py migrate

# Cargar datos de prueba
python manage.py loaddata fixtures/demo_data.json

# Servidor de desarrollo
python manage.py runserver

# Correr tests
pytest

# Compilar Tailwind (si usas CLI, no CDN)
npx tailwindcss -i static/css/input.css -o static/css/app.css --watch
```

## Convenciones

- **Modelos**: `PascalCase`, campos en `snake_case`
- **Views**: basadas en clases (CBV) donde sea natural, funciones (FBV) para HTMX partials
- **URLs**: `pedidos:lista`, `pedidos:crear`, `pedidos:editar`, `pedidos:eliminar`
- **Templates**: `{app}/{modelo}_lista.html`, `{app}/{modelo}_form.html`
- **Partials HTMX**: `partials/{nombre}.html`
- **Tests**: `tests/test_{app}.py`, clases `Test{Modelo}{Acción}`

## Variables de entorno requeridas (.env)

```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:pass@localhost:5432/smartsales
RESEND_API_KEY=
DEFAULT_FROM_EMAIL=
```
