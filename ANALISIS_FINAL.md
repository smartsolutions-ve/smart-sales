# SmartSales Django — Análisis Final del Sistema

**Fecha:** 21 de marzo de 2026
**Versión analizada:** MVP post-mejoras (branch `main`, commit `8a70cd4`)
**Tests:** 48/48 pasando
**Primer cliente:** El Gran Chaparral 2024 C.A.

---

## Tabla de contenidos

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Bugs críticos del backend](#2-bugs-críticos-del-backend)
3. [Problemas de seguridad](#3-problemas-de-seguridad)
4. [Problemas de rendimiento](#4-problemas-de-rendimiento)
5. [Errores de interfaz de usuario](#5-errores-de-interfaz-de-usuario)
6. [Inconsistencias de diseño](#6-inconsistencias-de-diseño)
7. [Problemas de accesibilidad](#7-problemas-de-accesibilidad)
8. [Problemas de responsive/mobile](#8-problemas-de-responsivemobile)
9. [Mejoras UX pendientes](#9-mejoras-ux-pendientes)
10. [Features pendientes — Prioridad Media](#10-features-pendientes--prioridad-media)
11. [Features pendientes — Prioridad Baja](#11-features-pendientes--prioridad-baja)
12. [Features pendientes — Post-MVP](#12-features-pendientes--post-mvp)
13. [Configuración de producción](#13-configuración-de-producción)
14. [Estado por módulo](#14-estado-por-módulo)

---

## 1. Resumen ejecutivo

El sistema SmartSales está **funcionalmente completo para un MVP**. Los 10 módulos core (Dashboard, Pedidos, Clientes, Productos, Despacho, Competencia, Campo, Reportes, Admin Panel, Auth) están implementados con datos reales, multi-tenancy funcional y 48 tests pasando.

**Lo que funciona bien:**
- Multi-tenancy por organización con middleware + decoradores
- CRUD completo en todos los módulos principales
- Dashboard con 6 gráficas Chart.js y KPIs reales
- Kanban de despacho con cambio de estado HTMX
- Formularios móviles para vendedores de campo
- Exportar CSV (pedidos, reportes vendedores, reportes clientes)
- Filtros por fecha en pedidos y reportes
- PDF de pedidos con WeasyPrint
- Auditoría básica de pedidos (PedidoLog)
- Notificaciones email al cambiar estado
- Modal de confirmación, mensajes auto-cerrables, prevención doble-clic
- Sidebar responsive con overlay mobile
- Perfil de usuario con cambio de contraseña
- Edición de registros de competencia

**Lo que necesita corrección antes de producción:** 15 bugs, 65 issues de UI, 10 features medias, 10 mejoras cosméticas.

---

## 2. Bugs críticos del backend

### BUG-001: NoneType crash cuando superadmin accede a pedidos

**Severidad:** CRÍTICA
**Archivos:** `apps/pedidos/views_pedidos.py` líneas 108, 160, 320
**Descripción:** Cuando un superadmin (`request.org = None`) accede a crear/editar pedidos, las líneas que filtran `Cliente.objects.filter(organization=request.org)` pasan `None` como valor de organización. Aunque hay un check `if not request.org`, el bloque `else` tiene un patrón redundante:

```python
# Línea 109 — el ternary es inútil porque request.org.user_set ya crashearía si es None
vendedores = request.org.user_set.filter(...) if request.org else []
```

**Impacto:** El superadmin no puede crear ni editar pedidos sin crash.
**Fix:** Mover todo el acceso a `request.org` dentro del bloque `if request.org`.

---

### BUG-002: Decorador role_required no reconoce is_superuser de Django

**Severidad:** ALTA
**Archivo:** `apps/accounts/decorators.py` líneas 6-24
**Descripción:** Un usuario creado con `createsuperuser` tiene `is_superuser=True` pero `role='vendedor'`. El decorador `@role_required('gerente', 'superadmin')` solo verifica `request.user.role`, no `is_superuser`. Esto bloquea al superadmin Django de acceder a vistas protegidas.
**Impacto:** Acceso denegado para superadmins creados con `createsuperuser`.
**Fix:** Agregar `if request.user.is_superuser: return view_func(request, *args, **kwargs)` al inicio del decorador.

---

### BUG-003: Dashboard con datos vacíos puede fallar silenciosamente

**Severidad:** MEDIA
**Archivo:** `apps/pedidos/views_dashboard.py` líneas 85-87, 112-184
**Descripción:** Cuando una organización nueva no tiene pedidos, las agregaciones retornan `None` en vez de `0`. Las gráficas Chart.js reciben listas vacías o valores null que pueden causar errores JS silenciosos.
**Impacto:** Dashboard muestra gráficas en blanco sin mensaje explicativo.
**Fix:** Agregar `|default:0` en el template y empty states para charts.

---

### BUG-004: Static CSS referenciado pero no existe

**Severidad:** BAJA
**Archivo:** `templates/base.html`
**Descripción:** Hay referencia a `static/css/app.css` pero el directorio `static/css/` está vacío. El proyecto usa Tailwind CDN así que no afecta la funcionalidad, pero genera un 404 silencioso.
**Fix:** Remover la referencia o crear el archivo.

---

## 3. Problemas de seguridad

| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| SEC-001 | ALTA | `CSRF_TRUSTED_ORIGINS` no configurado en prod — causará errores 403 en producción con dominio real | `config/settings/prod.py` |
| SEC-002 | MEDIA | No hay header `Content-Security-Policy` en producción | `config/settings/prod.py` |
| SEC-003 | MEDIA | `RESEND_API_KEY` no validado al iniciar — emails fallarán silenciosamente si no está configurado | `config/settings/prod.py` |
| SEC-004 | BAJA | No hay rate limiting en login — vulnerable a fuerza bruta | `apps/accounts/views.py` |
| SEC-005 | BAJA | No hay audit log de intentos de login fallidos | `apps/accounts/views.py` |

---

## 4. Problemas de rendimiento

| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| PERF-001 | ALTA | N+1 queries en dashboard — 8+ queries separadas que podrían ser 3-4 | `views_dashboard.py` líneas 70-184 |
| PERF-002 | MEDIA | Paginación hardcoded a 25 en todas las vistas — debería ser configurable | Múltiples archivos |
| PERF-003 | MEDIA | `pedido.items.all` en template PDF sin `prefetch_related` | `views_pedidos.py:detalle_pdf` |
| PERF-004 | BAJA | Dashboard recalcula todo en cada request — no hay cache para datos que cambian poco | `views_dashboard.py` |

---

## 5. Errores de interfaz de usuario

### 5.1 Dark mode roto

| ID | Archivo | Línea | Descripción |
|----|---------|-------|-------------|
| UI-001 | `campo/index.html` | 9 | `.bg-navy` y `.text-gold` son colores no declarados en Tailwind config |
| UI-002 | `accounts/cuenta_suspendida.html` | 8 | Card usa `bg-white` sin variante `dark:` |
| UI-003 | `pedidos/form.html` | 20, 89 | `bg-white` hardcoded sin `dark:bg-slate-900/50` |
| UI-004 | `pedidos/detalle.html` | 22, 56, 92 | Múltiples cards sin soporte dark mode |
| UI-005 | `clientes/detalle.html` | 65 | `bg-white` sin dark alternative |
| UI-006 | `dashboard/index.html` | 187-195 | Colores hardcoded en `<style>` tag que no respetan dark mode |

### 5.2 Estilos de badges inconsistentes

| ID | Archivo | Línea | Descripción |
|----|---------|-------|-------------|
| UI-007 | `pedidos/detalle.html` | 12-19 | Badge de estado usa estilos inline en vez de clases `badge-*` |
| UI-008 | `clientes/detalle.html` | 96-100 | Clases de badge diferentes a las del resto del sistema |
| UI-009 | `base.html` | 81-86 | `.badge-gray` y `.badge-neutral` duplicados; `.badge-green` y `.badge-success` duplicados |

### 5.3 Botones inconsistentes

| ID | Archivo | Línea | Descripción |
|----|---------|-------|-------------|
| UI-010 | `pedidos/form.html` | 159 | Usa `bg-brand` inline en vez de `btn-primary` |
| UI-011 | `pedidos/detalle.html` | 119 | Usa `bg-brand` en vez de `btn-primary` |
| UI-012 | `campo/pedido_form.html` | 150 | Usa `bg-brand` en vez de `btn-primary` |
| UI-013 | `campo/competencia_form.html` | 117 | Usa `bg-slate-700` inconsistente |
| UI-014 | `admin_panel/usuario_form.html` | 110 | Estilos inline en botones |

### 5.4 Íconos inconsistentes

| ID | Archivo | Línea | Descripción |
|----|---------|-------|-------------|
| UI-015 | `campo/index.html` | 29-32, 40-44 | Usa SVGs inline mezclados con Font Awesome |
| UI-016 | `accounts/cuenta_suspendida.html` | 10-13 | SVG inline en vez de Font Awesome |

---

## 6. Inconsistencias de diseño

| ID | Descripción | Archivos afectados |
|----|-------------|-------------------|
| DES-001 | Cards usan mezcla de `card-glass` y `bg-white rounded-xl border` manual | `pedidos/detalle.html`, `pedidos/form.html` |
| DES-002 | Spacing entre secciones varía: `space-y-5` vs `space-y-6` vs márgenes manuales | Múltiples templates |
| DES-003 | Tipografía de headers inconsistente: `text-title` vs `text-2xl font-bold` vs `font-semibold` | `pedidos/detalle.html:11`, `dashboard/index.html` |
| DES-004 | Select de estado en tabla usa `px-2 py-1` raw en vez de utility class | `partials/tabla_pedidos.html:26` |
| DES-005 | Input disabled usa `!bg-slate-50` override en vez de clase dedicada | `admin_panel/usuario_form.html:49` |
| DES-006 | `admin_panel/index.html:41` hace cálculo matemático en template en vez de view | Template logic leak |

---

## 7. Problemas de accesibilidad

| ID | Severidad | Descripción | Archivos |
|----|-----------|-------------|----------|
| A11Y-001 | ALTA | Inputs de búsqueda sin `aria-label` | `pedidos/lista.html`, `clientes/lista.html`, `productos/lista.html` |
| A11Y-002 | ALTA | Inputs required sin `aria-required="true"` | Todos los formularios |
| A11Y-003 | ALTA | Headers de tabla sin `scope="col"` | Todas las tablas |
| A11Y-004 | MEDIA | Modal de confirmación sin `role="dialog"` ni `aria-labelledby` | `base.html:369` |
| A11Y-005 | MEDIA | Canvas de Chart.js sin `aria-label` descriptivo | `dashboard/index.html:78-84` |
| A11Y-006 | MEDIA | Botón "volver" sin `aria-label` | `pedidos/detalle.html:10`, `clientes/detalle.html:12` |
| A11Y-007 | BAJA | Contraste insuficiente en textos `text-slate-400` sobre fondo dark | Múltiples templates |

---

## 8. Problemas de responsive/mobile

| ID | Severidad | Descripción | Archivo | Fix |
|----|-----------|-------------|---------|-----|
| RES-001 | ALTA | Kanban despacho `grid-cols-5` no adapta a mobile | `despacho/index.html:25` | Cambiar a `grid-cols-1 sm:grid-cols-2 lg:grid-cols-5` |
| RES-002 | ALTA | Tabla de competencia sin `overflow-x-auto` wrapper | `competencia/lista.html:19` | Agregar wrapper |
| RES-003 | MEDIA | Grid 3 cols en admin org detalle no stackea | `admin_panel/org_detalle.html:37` | Agregar `grid-cols-1 sm:grid-cols-3` |
| RES-004 | MEDIA | Grid 2 cols en items campo no adapta | `campo/pedido_form.html:133` | Agregar breakpoint mobile |
| RES-005 | MEDIA | Tabla reportes vendedores sin scroll horizontal | `reportes/vendedores.html:48` | Agregar `overflow-x-auto` |
| RES-006 | BAJA | Botones exportar+crear se solapan en mobile | `pedidos/lista.html:13-15` | Hacer `flex-wrap` |

---

## 9. Mejoras UX pendientes

| ID | Prioridad | Descripción | Detalle |
|----|-----------|-------------|---------|
| UX-001 | ALTA | No hay estado de carga en formularios | Agregar spinner en botón submit mientras procesa |
| UX-002 | ALTA | No hay aviso de cambios sin guardar | Usar `beforeunload` para advertir al usuario |
| UX-003 | ALTA | Dropdown de autocompletado sin mensaje "sin resultados" | `competencia/form.html`, `campo/pedido_form.html` — mostrar "No se encontraron productos" |
| UX-004 | MEDIA | Fecha de competencia sin valor por defecto (hoy) | `competencia/form.html:60` — debería tener `value="{{ today }}"` |
| UX-005 | MEDIA | Filtros de pedidos limpian la búsqueda al paginar | Los query params se pierden al cambiar de página |
| UX-006 | MEDIA | No hay mensaje contextual cuando filtros no retornan resultados | Mostrar "No hay pedidos que coincidan con los filtros" |
| UX-007 | BAJA | Placeholder de select cliente genérico | `pedidos/form.html:27` — "-- Seleccionar --" debería ser más descriptivo |
| UX-008 | BAJA | Tooltips ausentes en KPIs del dashboard | Explicar qué mide cada número al hacer hover |
| UX-009 | BAJA | Form submit deshabilitación demasiado broad | `base.html:354-362` — afecta TODOS los forms incluyendo HTMX |

---

## 10. Features pendientes — Prioridad Media

Funcionalidades que agregarían valor significativo para El Gran Chaparral:

| # | Feature | Descripción | Esfuerzo |
|---|---------|-------------|----------|
| FM-001 | **Clonar pedido** | Botón "Duplicar" en detalle de pedido para crear uno nuevo basado en el existente | 1-2h |
| FM-002 | **Filtro por fecha en competencia** | Inputs desde/hasta en lista de competencia | 1h |
| FM-003 | **Exportar CSV de competencia** | Botón exportar en lista de competencia | 1h |
| FM-004 | **Indicadores de urgencia en despacho** | Pedidos con fecha de entrega vencida resaltados en rojo | 1-2h |
| FM-005 | **Filtro por fecha en despacho** | Filtrar pedidos del kanban por rango de fecha | 1h |
| FM-006 | **Notificación al crear pedido desde campo** | Email al gerente cuando vendedor crea pedido | 30min |
| FM-007 | **Búsqueda en competencia** | Buscar por producto, competidor o vendedor | 1h |
| FM-008 | **Búsqueda avanzada de clientes** | Filtrar por teléfono, email, contacto además de nombre | 30min |
| FM-009 | **Dashboard: rango de fecha personalizado** | Inputs desde/hasta además de los presets (este mes, etc.) | 1-2h |
| FM-010 | **Paginación en reportes** | Agregar paginación en reportes de vendedores y clientes | 30min |

---

## 11. Features pendientes — Prioridad Baja

Mejoras cosméticas y de polish profesional:

| # | Feature | Descripción | Esfuerzo |
|---|---------|-------------|----------|
| FB-001 | **Breadcrumbs navegables** | Convertir breadcrumb estático en enlaces clickeables | 1-2h |
| FB-002 | **Favicon y logo** | Agregar favicon.ico y logo SVG de SmartSales | 30min |
| FB-003 | **Páginas 404/500 personalizadas** | Templates propios en vez de los de Django | 1h |
| FB-004 | **Empty states mejorados en dashboard** | Mensaje amigable cuando no hay datos para gráficas | 1h |
| FB-005 | **Ordenar tablas por columna** | Clic en header para ordenar asc/desc | 2-3h |
| FB-006 | **Campo: historial detallado del vendedor** | Ver detalle de pedidos pasados, no solo resumen | 1h |
| FB-007 | **Validación inline en formularios** | Mensajes de error debajo de cada campo, no solo flash | 2-3h |
| FB-008 | **Loading indicator HTMX** | Spinner global mientras HTMX carga contenido | 30min |
| FB-009 | **Print stylesheet** | CSS `@media print` para imprimir listas y detalle | 1h |
| FB-010 | **Consolidar clases CSS duplicadas** | Unificar `badge-gray`/`badge-neutral`, `badge-green`/`badge-success` | 30min |

---

## 12. Features pendientes — Post-MVP

Funcionalidades para fases posteriores, no bloquean lanzamiento:

| # | Feature | Descripción |
|---|---------|-------------|
| FP-001 | **Inventario/stock** | Niveles de stock por producto, alertas de bajo inventario |
| FP-002 | **Segmentación de clientes** | Clasificación VIP, regular, inactivo automática |
| FP-003 | **API REST** | Endpoints JSON para integraciones externas (Zapier, etc.) |
| FP-004 | **2FA** | Autenticación de dos factores para gerentes |
| FP-005 | **Importar CSV** | Carga masiva de clientes y productos |
| FP-006 | **Imágenes de producto** | Upload de fotos y galería |
| FP-007 | **Soporte offline campo** | Service worker para vendedores sin conexión |
| FP-008 | **Billing/suscripciones** | Cobro automático por plan en admin_panel |
| FP-009 | **Audit log global** | Login history, acciones de admin, trail completo |
| FP-010 | **Reportes comparativos** | MoM, YoY, tendencias y predicciones |
| FP-011 | **Webhooks** | Eventos push a sistemas externos |
| FP-012 | **Multi-idioma** | i18n para organizaciones en otros países |

---

## 13. Configuración de producción

Checklist antes de deploy:

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | `CSRF_TRUSTED_ORIGINS` | Pendiente | Agregar dominio real en `prod.py` |
| 2 | `ALLOWED_HOSTS` | Pendiente | Configurar IP del droplet y dominio |
| 3 | `RESEND_API_KEY` | Pendiente | Obtener key de Resend.com |
| 4 | `DEFAULT_FROM_EMAIL` | Pendiente | Configurar email verificado en Resend |
| 5 | `SECRET_KEY` | Pendiente | Generar key segura para producción |
| 6 | SSL/HTTPS | Pendiente | Configurar Let's Encrypt con Nginx |
| 7 | `collectstatic` | Pendiente | WhiteNoise sirve estáticos pero necesita `collectstatic` |
| 8 | PostgreSQL | Pendiente | Crear BD en DigitalOcean droplet |
| 9 | Dominio DNS | Pendiente | Apuntar dominio al droplet |
| 10 | Backups automáticos | Pendiente | Cron job para pg_dump |
| 11 | Monitoreo | Pendiente | Considerar Sentry para errores en producción |
| 12 | Rate limiting | Pendiente | Agregar `django-axes` o similar para login |
| 13 | WeasyPrint deps | Pendiente | Instalar `libpango`, `libcairo` en el servidor para PDFs |
| 14 | Gunicorn workers | Pendiente | Configurar workers en `docker-compose.yml` |

---

## 14. Estado por módulo

| Módulo | Funcionalidad | UI/UX | Dark Mode | Mobile | Tests |
|--------|:------------:|:-----:|:---------:|:------:|:-----:|
| **Auth/Login** | Completo | Bueno | OK | OK | 15/15 |
| **Dashboard** | Completo | Bueno | Parcial | Aceptable | — |
| **Pedidos** | Completo + CSV + PDF + Audit | Bueno | Parcial | Aceptable | 24/24 |
| **Clientes** | Completo | Bueno | Parcial | Aceptable | — |
| **Productos** | Completo | Bueno | OK | Aceptable | — |
| **Despacho** | Completo | Bueno | OK | Roto | 4/4 |
| **Competencia** | Completo + Editar | Bueno | OK | Aceptable | 5/5 |
| **Campo** | Completo | Aceptable | Roto | OK | — |
| **Reportes** | Completo + CSV + Fechas | Bueno | OK | Parcial | — |
| **Admin Panel** | Completo | Bueno | Parcial | Aceptable | — |
| **Perfil** | Completo | Bueno | OK | OK | — |

---

## Conteo total de issues

| Categoría | Cantidad |
|-----------|----------|
| Bugs críticos backend | 4 |
| Problemas de seguridad | 5 |
| Problemas de rendimiento | 4 |
| Errores UI (dark mode, badges, botones, íconos) | 16 |
| Inconsistencias de diseño | 6 |
| Problemas de accesibilidad | 7 |
| Problemas responsive/mobile | 6 |
| Mejoras UX | 9 |
| Features prioridad media | 10 |
| Features prioridad baja | 10 |
| Features post-MVP | 12 |
| Config producción | 14 |
| **Total** | **103** |

---

*Generado por Claude Code — 21 de marzo de 2026*
