# SmartSales — Reglas de Negocio

**Fecha:** Marzo 2026
**Stack:** Django 5.2 + PostgreSQL + HTMX + Alpine.js

---

## 1. Multi-tenancy

### RN-001: Aislamiento por organización
- Cada empresa cliente es una **Organización** (tenant)
- Todos los datos (pedidos, clientes, competencia) pertenecen a una organización
- Un usuario solo puede ver y modificar datos de su propia organización
- El superadmin puede ver y gestionar todas las organizaciones

### RN-002: Activación de organizaciones
- Una organización puede estar `activa = True` o `activa = False`
- Si `activa = False`, los usuarios de esa organización no pueden iniciar sesión
- Solo el superadmin puede activar o desactivar organizaciones
- La desactivación es el mecanismo de suspensión por falta de pago

### RN-003: Planes de servicio
- Planes disponibles: `starter`, `pro`, `enterprise`
- En el MVP, el plan es informativo — no hay límites técnicos aplicados automáticamente
- El superadmin asigna el plan manualmente al crear la organización

---

## 2. Usuarios y Roles

### RN-004: Roles del sistema

| Rol | Descripción | Acceso |
|-----|-------------|--------|
| `superadmin` | Administrador de SmartSales | Panel admin completo |
| `gerente` | Gerente de ventas del cliente | Dashboard completo |
| `vendedor` | Vendedor del cliente | Solo formulario de campo |

### RN-005: Creación de usuarios
- El superadmin crea cuentas para los gerentes de cada organización
- El gerente puede crear cuentas para sus vendedores (futuro, MVP: superadmin)
- Los vendedores no pueden crear cuentas

### RN-006: Inicio de sesión
- Auth por email + contraseña
- Si la organización está inactiva: acceso denegado con mensaje explicativo
- El superadmin no tiene `organization` — redirige a `/admin-panel/`
- El gerente redirige a `/dashboard/`
- El vendedor redirige a `/campo/`

---

## 3. Pedidos

### RN-007: Numeración de pedidos
- Formato: `PED-XXXX` (4 dígitos con cero a la izquierda)
- El número es único **por organización** (no global)
- La numeración es secuencial y no puede tener huecos
- El número se asigna al crear el pedido y nunca cambia
- Ejemplo: El Gran Chaparral puede tener PED-0001 y Distribuidora XYZ también puede tener PED-0001

### RN-008: Estados del pedido

```
Pendiente → Confirmado → En Proceso → Entregado
     ↓                                    ↑
  Cancelado ←──────────────────────────────
```

| Estado | Descripción |
|--------|-------------|
| `Pendiente` | Pedido creado, sin confirmación del cliente |
| `Confirmado` | Cliente confirmó el pedido |
| `En Proceso` | Pedido en preparación/producción |
| `Entregado` | Pedido entregado al cliente |
| `Cancelado` | Pedido cancelado (por cualquier razón) |

**Reglas de transición:**
- Solo el gerente puede cambiar estados
- Los pedidos `Cancelado` o `Entregado` no pueden cambiar de estado (terminal)
- Al marcar `Entregado`, el `estado_despacho` se cambia automáticamente a `Despachado`

### RN-009: Estados de despacho

| Estado Despacho | Descripción |
|-----------------|-------------|
| `Pendiente Despacho` | Aún no se coordina la entrega |
| `Programado` | Fecha de entrega coordinada |
| `En Tránsito` | Mercancía en camino |
| `Despachado` | Entregado al transportista/cliente |
| `Devuelto` | Pedido devuelto |

**Reglas:**
- El `estado_despacho` es independiente del `estado` del pedido
- Un pedido puede estar "Confirmado" y "En Tránsito" simultáneamente
- Solo pedidos con `estado != 'Cancelado'` aparecen en la vista de despacho
- Los pedidos con `estado_despacho = 'Pendiente Despacho'` aparecen con alerta roja

### RN-010: Total del pedido
- El `total` del pedido se calcula como la suma de `cantidad * precio` de todos sus items
- Se recalcula automáticamente al crear, editar o eliminar un item (signal de Django)
- El campo `total` en el modelo es un campo almacenado (no calculado en cada query)
- Los pedidos cancelados mantienen su total histórico

### RN-011: Items del pedido
- Un pedido debe tener **al menos 1 item** para poder guardarse
- Cada item tiene: `producto` (texto libre), `sku` (opcional), `cantidad`, `precio`
- El `subtotal` de cada item = `cantidad * precio` (property Python, no columna de BD)
- Los ítems se pueden agregar/quitar en el formulario antes de guardar

### RN-012: Referencia a competencia en pedido
- Opcional: el vendedor puede anotar en el pedido si vio un precio de la competencia
- Campo texto libre (`ref_competencia`)
- Esta referencia es diferente al módulo de Inteligencia de Competencia (más detallado)

---

## 4. Clientes

### RN-013: Gestión de clientes
- Los clientes pertenecen a una organización
- Un cliente puede tener múltiples pedidos
- Campos: `nombre` (requerido), `contacto`, `teléfono`, `email`, `dirección` (todos opcionales)
- No se pueden eliminar clientes que tengan pedidos asociados
- El nombre del cliente es único dentro de la organización

### RN-014: Estadísticas de clientes
- En la vista de clientes se muestra: total de pedidos y monto total acumulado
- Solo se cuentan pedidos con `estado != 'Cancelado'`

---

## 5. Inteligencia de Competencia

### RN-015: Registro de competencia
- Cualquier vendedor puede registrar un hallazgo de competencia desde el campo
- Campos: `fecha`, `cliente` (FK opcional), `vendedor` (auto del usuario logueado), `producto`, `competidor`, `precio_comp`, `precio_nuestro`, `accion_tomada`
- La diferencia de precio (`precio_nuestro - precio_comp`) se calcula en la vista
- Si `diferencia > 0`: somos más caros (color rojo)
- Si `diferencia < 0`: somos más baratos (color verde)

### RN-016: Análisis de competencia
- Los registros se muestran ordenados por fecha descendente
- El gerente puede ver todos los registros de su organización
- No se pueden editar registros de competencia (solo crear y eliminar)

---

## 6. Dashboard y Reportes

### RN-017: KPIs del dashboard

| KPI | Cálculo |
|-----|---------|
| Ventas totales | Suma de `total` de pedidos con `estado != 'Cancelado'` del mes actual |
| Pedidos activos | Count de pedidos con `estado IN ('Confirmado', 'En Proceso')` |
| Pendientes despacho | Count de pedidos con `estado_despacho = 'Pendiente Despacho'` y `estado != 'Cancelado'` |
| Tasa de cumplimiento | `(pedidos Entregados / total pedidos no Cancelados) * 100` |

### RN-018: Reporte por vendedor
- Métricas por vendedor: total vendido, cantidad de pedidos, pedidos entregados
- Solo pedidos con `estado != 'Cancelado'`
- Ordenado por total vendido descendente

### RN-019: Reporte por cliente
- Tabla de todos los clientes con su total acumulado de compras
- Solo pedidos con `estado != 'Cancelado'`

### RN-020: Filtros de periodo
- Dashboard muestra el mes actual por defecto
- El usuario puede filtrar por: este mes, mes anterior, últimos 3 meses, año actual, todo el tiempo

---

## 7. Formulario Móvil (Campo)

### RN-021: Acceso al formulario de campo
- Solo usuarios con `role = 'vendedor'` acceden a `/campo/`
- El vendedor NO puede acceder al dashboard gerencial
- El gerente SÍ puede acceder a `/campo/` además del dashboard

### RN-022: Registro de pedido desde el campo
- El vendedor selecciona el cliente (de los clientes de su organización) o escribe uno nuevo
- Si escribe un cliente nuevo, se crea automáticamente al guardar el pedido
- El vendedor es asignado automáticamente al pedido (el usuario logueado)
- El estado inicial es siempre `Pendiente`
- El estado de despacho inicial es siempre `Pendiente Despacho`
- El número PED-XXXX se asigna automáticamente

### RN-023: Registro de competencia desde el campo
- El vendedor puede registrar hallazgos de competencia desde el formulario móvil
- Acceso directo al formulario de competencia en la interfaz móvil

---

## 8. Billing / Pagos (MVP)

### RN-024: Modelo de negocio del MVP
- El cobro a clientes se gestiona **manualmente**
- No hay integración con pasarelas de pago en el MVP
- El superadmin activa/desactiva organizaciones manualmente al confirmar/perder el pago
- Métodos de pago aceptados: transferencia bancaria, pago móvil, USDT, efectivo (Venezuela)

### RN-025: Plan y precio
- El plan se registra en la organización pero no restringe funcionalidades en el MVP
- Precio referencial definido con cada cliente individualmente
- Facturación en USD o VES a tasa BCV según acuerdo

---

## 9. Seguridad

### RN-026: Protección de datos por organización
- Ninguna view puede devolver datos sin filtrar por `organization`
- Si un usuario intenta acceder a un recurso de otra organización → 404
- Las URLs con IDs de objetos siempre validan que pertenecen a la organización del usuario

### RN-027: Sesiones
- Sesión válida por 8 horas de inactividad (configurable)
- Al cerrar el navegador, la sesión expira
- El superadmin tiene sesión de 24 horas

---

## 10. Auditoría

### RN-028: Timestamps
- Todos los modelos tienen `created_at` (auto_now_add) y `updated_at` (auto_now)
- Los pedidos registran quién los creó (`created_by`) y quién los modificó por última vez (`updated_by`)

### RN-029: Soft delete (futuro)
- En el MVP, los pedidos se pueden eliminar permanentemente solo si están en estado `Pendiente`
- Los pedidos en otros estados solo pueden cancelarse, no eliminarse
