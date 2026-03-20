# SmartSales Django — Planificación del Proyecto

**Stack:** Django 5.2 + PostgreSQL + HTMX + Alpine.js
**Equipo:** 1 desarrollador junior + Claude Pro
**Deploy:** DigitalOcean Droplet $6/mes (ya disponible)

---

## Criterios de éxito del MVP

- [ ] El Gran Chaparral usando el sistema en producción sin fallos críticos por 30 días
- [ ] Tiempo de respuesta del dashboard < 500ms (en warm)
- [ ] Formulario móvil funcional en Android Chrome
- [ ] Superadmin puede onboardear un nuevo cliente en < 10 minutos
- [ ] 1-3 clientes adicionales activos en los primeros 90 días

---

## Fase 0 — Setup inicial (Día 1-2)

- [x] Definición de stack y arquitectura
- [x] Documentación inicial (ARCHITECTURE.md, REGLAS_NEGOCIO.md, REQUIREMENTS.md)
- [ ] Crear repositorio GitHub: `smartsales-ve/smartsales-django`
- [ ] Inicializar proyecto Django con estructura de apps
- [ ] Configurar entorno virtual + requirements.txt
- [ ] Setup settings (base/dev/prod) con django-environ
- [ ] Configurar pytest-django
- [ ] Primer commit con scaffold limpio

**Entregable:** Proyecto Django que corre `python manage.py runserver` sin errores

---

## Fase 1 — Auth y Multi-tenancy (Día 3-5)

- [ ] Custom User model (AbstractUser + organization + role)
- [ ] Modelo Organization
- [ ] TenantMiddleware
- [ ] Decoradores: `@role_required`, `@superadmin_required`
- [ ] Vista de Login (email + password)
- [ ] Vista de Logout
- [ ] Redirect por rol al hacer login
- [ ] Template base con Tailwind CDN + HTMX + Alpine.js
- [ ] Template de login
- [ ] Migraciones iniciales

**Tests a escribir:**
- `test_login_correcto` → redirige según rol
- `test_login_org_inactiva` → acceso denegado
- `test_tenant_aislamiento` → usuario A no ve datos de org B

**Entregable:** Login funcional, redirección por rol, middleware de tenant activo

---

## Fase 2 — Modelos core + Admin panel (Día 6-9)

- [ ] Modelos: Cliente, Pedido, PedidoItem, CompetenciaRegistro
- [ ] Signal `recalcular_total_pedido` (post_save / post_delete de PedidoItem)
- [ ] Función `generar_numero_pedido(organization)` con protección de concurrencia
- [ ] Django Admin configurado para superadmin (Organization, User)
- [ ] Panel `/admin-panel/` con vistas custom para superadmin
  - [ ] Lista de organizaciones con KPIs
  - [ ] Crear organización
  - [ ] Gestionar usuarios de una org
  - [ ] Activar/desactivar organización
- [ ] Fixtures: datos de El Gran Chaparral (clientes, vendedores, 20 pedidos demo)

**Tests a escribir:**
- `test_total_recalculado_al_agregar_item`
- `test_total_recalculado_al_eliminar_item`
- `test_numero_pedido_unico_por_org`
- `test_superadmin_ve_todas_las_orgs`

**Entregable:** Modelo de datos completo con admin funcional

---

## Fase 3 — Dashboard gerencial (Día 10-13)

- [ ] Vista `/dashboard/` con KPIs:
  - [ ] Ventas totales del mes
  - [ ] Pedidos activos
  - [ ] Pendientes de despacho
  - [ ] Tasa de cumplimiento
- [ ] Gráfico de barras por vendedor (CSS puro como en el HTML original)
- [ ] Lista de pedidos urgentes (próximos a vencer)
- [ ] Filtro de periodo (mes actual, mes anterior, 3 meses, año, todo)
- [ ] Template `dashboard/index.html` con Alpine.js para el filtro

**Tests a escribir:**
- `test_kpis_solo_pedidos_no_cancelados`
- `test_kpis_filtro_por_periodo`
- `test_dashboard_solo_org_actual`

**Entregable:** Dashboard con KPIs reales del tenant

---

## Fase 4 — Módulo de Pedidos (Día 14-18)

- [ ] Lista de pedidos con búsqueda y filtros (HTMX para filtrado sin recarga)
- [ ] Modal crear/editar pedido con Alpine.js:
  - [ ] Selector de cliente (existente o nuevo)
  - [ ] Items dinámicos (agregar/quitar filas)
  - [ ] Total calculado en tiempo real
- [ ] Cambio de estado inline (HTMX)
- [ ] Cambio de estado despacho inline (HTMX)
- [ ] Detalle de pedido
- [ ] Eliminar pedido (solo si está en Pendiente)
- [ ] Server Actions equivalentes: views con POST

**Tests a escribir:**
- `test_crear_pedido_con_items`
- `test_no_crear_pedido_sin_items`
- `test_cambiar_estado_valido`
- `test_no_cambiar_estado_entregado`
- `test_eliminar_solo_pendiente`
- `test_pedido_solo_visible_en_su_org`

**Entregable:** CRUD completo de pedidos funcional

---

## Fase 5 — Despacho y Logística (Día 19-21)

- [ ] Vista `/despacho/` tipo Kanban (columnas por estado_despacho)
- [ ] Indicadores de urgencia por color según `fecha_entrega`
- [ ] Cambio de estado despacho desde Kanban (HTMX)
- [ ] Alerta de pedidos pendientes de despacho
- [ ] Filtro por vendedor

**Tests a escribir:**
- `test_despacho_solo_pedidos_no_cancelados`
- `test_cambiar_estado_despacho`
- `test_urgencia_por_fecha`

**Entregable:** Vista de despacho Kanban funcional

---

## Fase 6 — Clientes y Competencia (Día 22-24)

**Clientes:**
- [ ] Lista de clientes con total acumulado
- [ ] Crear/editar cliente
- [ ] Validación: no eliminar con pedidos activos

**Competencia:**
- [ ] Lista de registros de competencia
- [ ] Formulario de nuevo registro
- [ ] Cálculo de diferencia de precio
- [ ] Color rojo/verde según diferencia

**Tests a escribir:**
- `test_no_eliminar_cliente_con_pedidos`
- `test_diferencia_precio_competencia`

**Entregable:** Módulos de clientes y competencia operativos

---

## Fase 7 — Formulario Móvil (Día 25-27)

- [ ] Ruta `/campo/` con layout móvil (sin sidebar)
- [ ] Formulario de pedido optimizado para móvil con Alpine.js
- [ ] Selector de cliente con búsqueda rápida
- [ ] Items con teclado numérico en móvil
- [ ] Confirmación de éxito con opción de registrar otro
- [ ] Formulario de competencia desde el campo
- [ ] Restricción: vendedor solo accede a `/campo/`

**Tests a escribir:**
- `test_vendedor_redirigido_a_campo`
- `test_vendedor_no_accede_a_dashboard`
- `test_pedido_campo_asigna_vendedor_logueado`

**Entregable:** Formulario móvil usable en Android Chrome

---

## Fase 8 — Reportes (Día 28-30)

- [ ] `/reportes/vendedores/` — métricas por vendedor
- [ ] `/reportes/clientes/` — top clientes por monto

**Entregable:** Módulo de reportes funcional

---

## Fase 9 — Testing y Calidad (Día 31-34)

- [ ] Completar cobertura de tests al 80%+
- [ ] Tests E2E básicos con Playwright (login, crear pedido, cambiar estado)
- [ ] Revisar queries N+1 con django-debug-toolbar en dev
- [ ] Agregar índices de BD donde corresponda

---

## Fase 10 — Deploy en DigitalOcean (Día 35-37)

- [ ] Dockerfile
- [ ] docker-compose.yml (web + db + nginx)
- [ ] nginx.conf y conf.d/smartsales.conf
- [ ] Variables de entorno de producción
- [ ] Script de deploy (`deploy.sh`)
- [ ] SSL con Let's Encrypt
- [ ] Backup automático de PostgreSQL (cron)
- [ ] Renovación automática de SSL (cron)
- [ ] Verificar checklist de producción

**Entregable:** Sistema en producción accesible por dominio con HTTPS

---

## Modelo de precios

| Plan | Usuarios | Precio referencial |
|------|----------|-------------------|
| Starter | hasta 3 vendedores | acordar con cliente |
| Pro | hasta 10 vendedores | acordar con cliente |
| Enterprise | ilimitado | acordar con cliente |

*Pagos: transferencia bancaria, pago móvil, USDT, efectivo*
*Divisa: USD o VES a tasa BCV*

---

## Roadmap post-MVP (Fase 11+)

- [ ] Exportar pedidos a Excel/PDF
- [ ] Notificaciones por WhatsApp (Twilio / UltraMsg) al cambiar estados
- [ ] Billing automatizado con Cryptomus (USDT) o BTCPay
- [ ] API REST para integración con apps externas
- [ ] PWA instalable para formulario de campo
