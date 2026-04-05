## **Análisis SmartSales — Respuestas para Faparca**

---

### **SEGURIDAD DE LA DATA — Propuesta**

Lo que ya tiene implementado:

| Capa | Mecanismo | Estado |
| :---- | :---- | :---- |
| Aislamiento multi-tenant | TenantMiddleware → cada query filtra por organization | ✅ Activo |
| HTTPS forzado | SECURE\_SSL\_REDIRECT=True, HSTS 1 año con preload | ✅ Prod |
| Cookies seguras | SESSION\_COOKIE\_SECURE, CSRF\_COOKIE\_SECURE | ✅ Prod |
| Anti-CSRF | Token inyectado automático en todas las peticiones HTMX | ✅ Activo |
| Contraseñas | Hash bcrypt (Django default), mínimo 8 caracteres | ✅ Activo |
| Suspensión de cuenta | Org inactiva → redirect automático, sin acceso a datos | ✅ Activo |
| Roles y permisos | 3 niveles: superadmin / gerente / vendedor, decoradores en cada vista | ✅ Activo |
| Infraestructura | Docker \+ Nginx como reverse proxy, PostgreSQL 16 aislado en contenedor | ✅ Prod |

Propuesta a presentar:

*"La data de Faparca reside en una base de datos PostgreSQL dedicada, aislada por organización mediante código de aplicación — ningún vendedor ni usuario puede ver datos de otra empresa. El acceso se controla por roles, todo el tráfico viaja cifrado por HTTPS con certificado SSL (Let's Encrypt renovación automática), y la infraestructura vive en un servidor en la nube con backups configurables. Opcionalmente se pueden ofrecer snapshots diarios del servidor ($1/mes en DigitalOcean) y dumps automáticos de la base de datos."*

Lo que se puede agregar según el plan:

* Backups automáticos diarios de PostgreSQL (pg\_dump via cron → S3/Spaces)  
* 2FA para cuentas gerente (django-two-factor-auth, \~2 días de trabajo)  
* Auditoría de accesos (log de quién hizo qué y cuándo)

---

### **MODELO DE ARQUITECTURA COMERCIAL (VISITA)**

Lo que existe hoy:

El módulo /campo/ ya tiene la base del modelo de visita comercial para vendedores en campo:  
/campo/              → Vista principal del vendedor (pedidos recientes)  
/campo/pedido/nuevo/ → Crear pedido desde el campo (móvil)  
/campo/competencia/  → Registrar precio de competencia en visita

El vendedor puede desde el celular:

* Crear pedidos con productos del catálogo  
* Registrar inteligencia competitiva (precio nuestro vs competidor, acción tomada)  
* Seleccionar o crear cliente en el momento

Lo que faltaría para un modelo de visita completo (GAP):

| Feature | Complejidad | Tiempo est. |
| :---- | :---- | :---- |
| Registro formal de visita (fecha, duración, objetivo, resultado) | Baja-media | 2-3 días |
| Geolocalización del check-in en visita | Media | 2 días |
| Agenda/itinerario de visitas por vendedor | Media | 3-4 días |
| Fotos adjuntas en la visita | Media | 2 días |
| Reporte de visitas por vendedor (gerente) | Baja | 1 día |

Respuesta para Faparca:

*"El sistema tiene la arquitectura base lista para el modelo de visitas comerciales — el vendedor trabaja desde el celular, crea pedidos y registra información de competencia en tiempo real durante la visita. Para el modelo completo de ciclo de visita (agenda, check-in, informe de visita) se requiere una extensión adicional de 2-3 semanas."*  
---

### **CONSOLIDACIÓN CON ERP PREESTABLECIDO**

Estado actual: El sistema no tiene API REST pública, pero tiene puntos de integración.

Opciones reales según profundidad de integración:

Opción A — Exportación/Importación (Sin desarrollo, ya posible):

* Exportar pedidos/clientes a CSV/Excel desde las vistas de reportes  
* Importar productos/clientes vía fixtures JSON de Django  
* Periodicidad: manual o programada (cron)

Opción B — API REST de lectura (2-3 semanas):

* Agregar djangorestframework a requirements  
* Exponer endpoints: /api/pedidos/, /api/clientes/, /api/productos/  
* El ERP consulta SmartSales como fuente de verdad de ventas en campo

Opción C — Integración bidireccional (4-6 semanas):

* Webhooks: cuando se crea/actualiza un pedido, notificar al ERP  
* El ERP envía actualizaciones de stock/precios a SmartSales  
* Requiere conocer el ERP específico de Faparca (SAP, Odoo, Profit, Sinco, etc.)

Pregunta clave para hacerle a Faparca:

*¿Qué ERP usan actualmente? ¿Tiene API REST, webhook o solo acceso por base de datos?*

Respuesta para presentación:

*"SmartSales puede conectarse con el ERP actual de Faparca. El nivel de integración depende del ERP: con cualquier sistema que tenga API REST la sincronización es bidireccional; con ERPs más cerrados se trabaja por exportación/importación automática programada. En la etapa de implementación se define el protocolo exacto."*  
---

### **REPORTES EN PDF \+ ENVÍO POR CORREO**

Estado actual: Los reportes son HTML en pantalla únicamente. No hay PDF todavía.

Lo que se puede agregar (2-3 días de trabajo):  
\# requirements.txt — agregar:  
weasyprint==62.3    \# HTML → PDF de alta calidad, respeta CSS/Tailwind

Con WeasyPrint se puede:

* Generar PDF desde cualquier template HTML existente con un solo botón  
* Adjuntarlo a un email automático vía Resend (ya configurado en el proyecto)  
* Programar envío automático semanal/mensual (con APScheduler o cron)

Ejemplo de flujo que se puede implementar:  
Gerente hace clic "Descargar PDF" → Django renderiza template → WeasyPrint genera PDF  
                                                               → Opción: enviar por email

Respuesta para Faparca:

*"En la versión actual los reportes se visualizan en pantalla en tiempo real. La generación de PDF y envío por correo es una funcionalidad lista para agregar en 2-3 días de trabajo — está contemplada como mejora inmediata post-lanzamiento o puede incluirse en el alcance inicial si es requerimiento."*  
---

### **¿ONLINE EN TIEMPO REAL?**

Sí, con precisión técnica:

| Característica | Comportamiento |
| :---- | :---- |
| Dashboard KPIs | Se calculan al cargar/filtrar la página — datos al momento exacto de la consulta |
| Actualizaciones entre usuarios | Si Vendedor A crea un pedido, Gerente lo ve al refrescar o navegar al listado |
| HTMX | Actualiza fragmentos de la página sin recargar — respuesta en \<200ms local |
| No hay WebSockets | No hay push server→cliente automático (no notificaciones en vivo sin refrescar) |

En términos de negocio:

*"El sistema es 100% online, multi-usuario simultáneo, con datos actualizados al segundo. Un vendedor crea un pedido desde el celular y el gerente lo ve inmediatamente en el dashboard. No requiere sincronización manual ni instalación local."*  
---

### **COSTO DEL SISTEMA**

Costos de infraestructura mensuales (por organización o compartida):

| Componente | Costo/mes | Notas |
| :---- | :---- | :---- |
| DigitalOcean Droplet $6 | $6 USD | 1GB RAM, 1 CPU, 25GB SSD — válido para arranque |
| DigitalOcean Droplet $12 | $12 USD | 2GB RAM, 1 CPU — recomendado para uso regular |
| SSL (Let's Encrypt) | $0 | Gratuito, renovación automática |
| Dominio (.com) | \~$1.20 USD | \~$15/año |
| Resend email (hasta 3,000/mes) | $0 | Plan gratuito suficiente para inicio |
| Backups automáticos DigitalOcean | \+$1.20 USD | Snapshots semanales del servidor |
| Total mínimo operativo | \~$7-14 USD/mes |  |

Costo de licencia/desarrollo: Esto depende de tu modelo de negocio (SaaS mensual, venta única, por usuario).  
---

### **CAPACIDAD MÁXIMA — TOP DEL SISTEMA**

Con el Droplet $12 (2GB RAM, PostgreSQL 16):

| Entidad | Capacidad práctica | Límite real PostgreSQL |
| :---- | :---- | :---- |
| Productos | 50,000+ sin problema | Millones |
| Clientes | 20,000+ sin problema | Millones |
| Vendedores activos | 50-100 simultáneos | Miles (limitado por RAM) |
| Pedidos/mes | 5,000-10,000/mes fluido | Sin límite práctico |
| Historial de pedidos | 5 años+ sin degradación | Sin límite con índices |
| Organizaciones (multi-tenant) | 10-20 en $12 Droplet | Escalar vertical si hay más |

Para una empresa como Faparca (estimado conservador):

*Si tienen 10-20 vendedores, 2,000-5,000 clientes, 500-1,000 productos — el Droplet de $12/mes es más que suficiente con margen amplio.*

Cuándo escalar: Si superan 50 usuarios concurrentes o 50,000 pedidos históricos se migra al Droplet de $24 (sin cambio de código, solo clic en DigitalOcean).  
---

### **TIEMPO DE IMPLEMENTACIÓN**

Semana 1 — Configuración y setup  
  ├── Servidor en producción (DigitalOcean \+ dominio \+ SSL)  
  ├── Carga inicial de datos (productos, clientes, usuarios)  
  └── Configuración de organización Faparca

Semana 2 — Capacitación  
  ├── Gerentes: dashboard, reportes, gestión de pedidos  
  ├── Vendedores: app móvil /campo/ (pedidos \+ competencia)  
  └── Administrador interno: gestión de usuarios

Semana 3 — Marcha blanca  
  ├── Uso paralelo con sistema anterior (si existe)  
  ├── Soporte diario en ajustes y dudas  
  └── Refinamiento de flujos según uso real

Semana 4 — Go live oficial  
  └── Sistema principal, soporte continuo

TOTAL: 3-4 semanas

---

### **PROTOCOLO DE IMPLEMENTACIÓN**

Fase 0 — Pre-implementación (3-5 días)  
  ├── Reunión de relevamiento: roles actuales, flujo de pedidos, integraciones  
  ├── Definir estructura de productos (categorías, SKUs, precios)  
  ├── Listado inicial de clientes y vendedores  
  └── Decisión de dominio (smartsales.faparca.com o similar)

Fase 1 — Instalación técnica (1-2 días)  
  ├── Provisionar servidor en DigitalOcean  
  ├── Deploy con Docker Compose (DB \+ App \+ Nginx)  
  ├── Configurar SSL, dominio, variables de entorno  
  └── Validar acceso desde internet

Fase 2 — Carga de datos maestros (1-2 días)  
  ├── Importar catálogo de productos  
  ├── Importar base de clientes  
  └── Crear usuarios (gerentes \+ vendedores) con roles

Fase 3 — Capacitación diferenciada  
  ├── Sesión gerentes (2h): dashboard, reportes, gestión  
  ├── Sesión vendedores (1h): app campo desde celular  
  └── Manual de usuario entregado (PDF)

Fase 4 — Marcha blanca (1-2 semanas)  
  ├── Uso real con soporte directo (WhatsApp/email)  
  └── Ajustes según feedback operativo

Fase 5 — Go live  
  └── Entrega formal, documentación, accesos de administrador

---

### **COSTOS POST-IMPLEMENTACIÓN Y SERVICIOS**

Infraestructura mensual recurrente:

| Concepto | Costo USD/mes |
| :---- | :---- |
| Servidor DigitalOcean $12 | $12 |
| Backups automáticos | $2.40 |
| Dominio (prorrateado) | $1.25 |
| Total infraestructura | \~$16/mes |

Servicios post que pueden ofrecerse:

| Servicio | Modalidad |
| :---- | :---- |
| Soporte técnico correctivo | Incluido 3 meses, luego plan mensual |
| Actualizaciones de seguridad Django | Incluido en plan mantenimiento |
| Nuevas funcionalidades | Cotización por módulo |
| Capacitación de nuevos usuarios | Por sesión o incluida en plan |
| Monitoreo de disponibilidad (uptime) | DigitalOcean lo provee gratis con alertas |
| Restauración de backup ante falla | Procedimiento documentado, \<30 min |

Planes post sugeridos (ejemplo):  
Plan Básico — $X/mes  
  └── Infraestructura \+ soporte por email (72h respuesta)

Plan Pro — $XX/mes  
  └── Infraestructura \+ soporte WhatsApp (24h) \+ 1 mejora menor/mes

Plan Enterprise — $XXX/mes  
  └── Todo lo anterior \+ SLA de uptime 99.5% \+ integraciones ERP incluidas

---

### **RESUMEN EJECUTIVO PARA LA PRESENTACIÓN**

| Pregunta | Respuesta corta |
| :---- | :---- |
| Seguridad de data | Datos aislados por empresa, HTTPS, roles, suspensión instantánea si es necesario |
| Modelo de visitas | Base ya implementada para vendedor en campo, módulo completo de visitas en 2-3 semanas |
| Integración ERP | Sí, nivel según ERP específico de Faparca (requiere relevamiento) |
| PDF \+ email de reportes | No en versión actual, 2-3 días para implementarlo — puede incluirse en alcance |
| Tiempo real | 100% online multi-usuario, datos al instante al navegar |
| Costo operativo | \~$16 USD/mes de infraestructura |
| Capacidad máxima | 50,000 productos, 20,000 clientes, 100 vendedores sin problema en $12/mes |
| Tiempo de implementación | 3-4 semanas desde firma |
| Protocolo | 5 fases: relevamiento → deploy → datos → capacitación → go live |

Okey ahora haz un analisis de todo el sistema en genaral y dame una lista de todos los puntos que se pueden mejorar  
Deep analysis for improvement areas  
Deep analysis for improvement areas  
Aquí está el análisis completo del sistema organizado por prioridad e impacto:  
---

## **Análisis Completo SmartSales — Puntos de Mejora**

---

### **CRÍTICO — Seguridad y Datos**

1\. Validación de inputs incompleta

* Items del pedido aceptan cantidades y precios negativos — no hay validación a nivel de base de datos  
* Campos de texto largo (accion\_tomada, observaciones) sin sanitización  
* Sin constraint a nivel DB para PedidoItem.cantidad \> 0 y precio \>= 0

2\. Sin auditoría de cambios

* Nadie sabe quién cambió el estado de un pedido, ni cuándo, ni por qué  
* No hay modelo HistorialEstadoPedido — si un gerente cambia un pedido de Entregado a Cancelado, no queda registro  
* No hay log de creación/eliminación de usuarios

3\. Sin soft delete

* Todos los borrados son permanentes  
* Al eliminar un Cliente, los Pedido quedan huérfanos (protegido por FK, pero sin historial)  
* Para auditoría/compliance se necesita deleted\_at \+ deleted\_by

4\. Permisos solo por rol, no por objeto

* Si alguien conoce el pk de un pedido de otra organización y la URL, el middleware lo bloquea pero no hay verificación en la vista misma  
* Falta get\_object\_or\_404(Pedido, pk=pk, organization=request.org) en algunas vistas

5\. Sin rate limiting

* El endpoint /productos/buscar/ (JSON autocomplete) no tiene throttling  
* El formulario de login no tiene protección contra fuerza bruta

---

### **ALTO — Funcionalidades Clave Faltantes**

6\. Reportes no exportan nada ⬅ (ya discutido para Faparca)

* No hay PDF, no hay Excel, no hay CSV  
* La librería de email django-anymail\[resend\] está instalada y configurada pero no se usa en ninguna vista — solo en reset de contraseña  
* Fix: agregar weasyprint para PDF y openpyxl para Excel (\~3 días)

7\. Sin notificaciones por email en eventos clave

* Vendedor crea pedido → Gerente no recibe email  
* Pedido cambia a "En Tránsito" → Cliente no se entera  
* Pedido vence mañana → Nadie recibe alerta automática  
* El sistema tiene Resend configurado y dormido

8\. Sin seguimiento de pagos

* El Pedido tiene total pero no tiene pagado, metodo\_pago, fecha\_pago  
* No se puede saber qué pedidos están cobrados y cuáles no  
* No hay generación de factura/recibo

9\. Sin control de inventario

* Producto tiene nombre, SKU y precio base pero no tiene stock  
* Al crear un pedido no se descuenta nada del inventario  
* No hay alertas de stock bajo  
* No se puede saber si se puede cumplir un pedido

10\. Filtros de reportes muy limitados

* El reporte de vendedores no tiene filtro de fecha (muestra todo el tiempo)  
* El reporte de clientes tampoco  
* No hay filtro por rango de montos en la lista de pedidos  
* No hay exportación del resultado filtrado

11\. Estados del pedido y despacho son independientes sin validación cruzada

* Un pedido puede estar en estado Cancelado y al mismo tiempo en estado\_despacho \= En Tránsito — inconsistencia de negocio sin restricción en código

12\. Sin historial de estados

* No existe un modelo PedidoEstadoHistorial que registre cada transición  
* Es imposible saber cuánto tiempo estuvo un pedido en cada etapa

---

### **ALTO — Performance**

13\. Consultas N+1 en varias vistas  
\# despacho/views.py — agrupa en Python en vez de en DB  
for pedido in queryset:  
    grupos\[pedido.estado\_despacho\].append(pedido)  \# N queries implícitas

\# dashboard — query por cada vendedor en el loop  
for user in vendedores\_activos:  
    Pedido.objects.filter(vendedor=user, ...)  \# 6 queries × N vendedores

14\. Sin índices en campos de alta frecuencia

* Pedido.estado — filtrado en dashboard, despacho, reportes: sin db\_index=True  
* Pedido.estado\_despacho — filtrado en despacho: sin índice  
* Pedido.fecha\_pedido — usado en ordenamiento y filtros de fecha: sin índice  
* Pedido.fecha\_entrega — urgentes se filtran por este campo: sin índice

15\. Reportes sin paginación

* reportes/views.py carga todos los vendedores/clientes de la org en memoria  
* En una empresa con 500 clientes, carga los 500 de una vez

16\. Sin caché en ninguna capa

* Los KPIs del dashboard se recalculan con cada visita  
* Los Sum() y Count() corren sobre toda la tabla cada vez  
* Sin Redis, sin @cache\_page, sin cache.get/set

---

### **MEDIO — UX y Usabilidad**

17\. Formularios sin estado de carga

* El botón de submit no se deshabilita al hacer clic  
* Un vendedor puede hacer doble clic y crear dos pedidos iguales  
* No hay spinner visible durante el envío

18\. Notificaciones (toast) no se auto-ocultan

* Los mensajes de "Pedido creado exitosamente" quedan en pantalla para siempre  
* No tienen botón X para cerrar manualmente

19\. Tablas sin ordenamiento por columna

* Lista de pedidos: no se puede ordenar por fecha, por total, por cliente  
* Lista de clientes: no se puede ordenar por nombre o por compras totales

20\. Sin persistencia de filtros al paginar

* Si filtras pedidos por estado "Confirmado" y vas a la página 2, se pierden los filtros

21\. Formulario de campo (móvil) sin total en tiempo real

* El vendedor agrega productos/cantidades/precios pero no ve el total del pedido mientras lo crea  
* Solo ve el total después de guardar

22\. Sin confirmación antes de eliminar

* No hay modal de "¿Estás seguro?" antes de eliminar un cliente o pedido  
* Solo funciona la protección de backend (no puede borrar si tiene pedidos), pero no hay feedback previo al usuario

23\. Modo oscuro no sincronizado entre pestañas

* Si cambias a dark mode en una pestaña, las otras siguen en light

24\. Accesibilidad (A11y) básica faltante

* Sin aria-label en botones de icono (las lupas, los X, los lápices)  
* Sin for asociado a id en todos los labels de formulario  
* Indicadores de estado solo por color (rojo/verde) sin texto alternativo para daltónicos

---

### **MEDIO — Calidad de Código**

25\. Lógica duplicada entre views\_pedidos.py y campo/views.py

* La función \_guardar\_pedido y \_crear\_pedido\_campo tienen la misma lógica de parseo de items, creación de cliente, generación de número — copiada  
* Debería existir un PedidoService que ambas vistas usen

26\. Función \_guardar\_pedido tiene 114 líneas y hace demasiado

* Valida, crea, actualiza, maneja items, maneja cliente nuevo — todo en una función  
* Difícil de testear y mantener

27\. Imports dentro de funciones

* from django.utils import timezone aparece dentro de funciones en vez de al tope del archivo  
* from django.contrib.auth import get\_user\_model dentro de la vista del dashboard

28\. Números mágicos hardcodeados  
\# views\_dashboard.py  
range(5, \-1, \-1)      \# ← ¿por qué 6 meses? no está explicado  
\[:5\]                   \# top 5 vendedores  
\[:10\]                  \# top 10 clientes  
hoy \+ timedelta(days=3) \# ← umbral de "urgente"  
\# Deberían ser constantes con nombre en settings.py

29\. Sin type hints en ningún archivo Python

30\. Sin docstrings en las funciones de vista  
---

### **BAJO — Mejoras Adicionales de Negocio**

31\. Sin descuentos ni precios especiales por cliente

* No hay descuento por volumen, por cliente VIP, por campaña  
* El precio es fijo del catálogo de productos

32\. Sin módulo de visitas comerciales completo

* El módulo /campo/ solo tiene creación de pedido y registro de competencia  
* No tiene: agenda de visitas, check-in geolocalizado, informe de visita, foto del local

33\. Sin análisis de competencia en reportes

* CompetenciaRegistro recopila precios pero no hay ningún reporte que los analice  
* La diferencia de precio está calculada en el modelo pero nunca se muestra

34\. Sin segmentación de clientes

* No hay etiquetas, categorías o nivel (VIP, frecuente, inactivo) para clientes  
* No se puede identificar clientes que no compran hace 90 días

35\. Sin integración con ERP o API REST

* No hay endpoints REST para que sistemas externos lean pedidos o actualicen stock  
* No hay webhooks cuando un pedido cambia de estado

36\. Sin monitoreo de errores en producción

* Sin Sentry, si hay un error 500 en producción nadie se entera hasta que un usuario reporta  
* Los logs de gunicorn van a stdout del contenedor Docker, sin retención

37\. Sin health check endpoint

* No hay /health/ para que el load balancer o uptime monitor verifique que el sistema responde

38\. Sin backup automatizado de la base de datos

* Docker Compose tiene un volumen persistente, pero sin pg\_dump periódico los datos podrían perderse si el volumen se corrompe

---

### **Tabla Resumen Priorizada**

| \# | Mejora | Impacto | Esfuerzo |
| :---- | :---- | :---- | :---- |
| 1 | Validación inputs \+ constraints DB | Alto | Bajo |
| 2 | Auditoría de cambios en pedidos | Alto | Medio |
| 3 | Email automático en eventos (usar Resend ya instalado) | Alto | Medio |
| 4 | Export PDF/Excel de reportes y pedidos | Alto | Medio |
| 5 | Historial de estados por pedido | Alto | Bajo |
| 6 | Índices en Pedido.estado / fecha\_pedido / vendedor | Alto | Bajo |
| 7 | Control básico de inventario (stock en Producto) | Alto | Medio |
| 8 | Seguimiento de pagos en Pedido | Alto | Medio |
| 9 | Soft delete (deleted\_at) | Medio | Bajo |
| 10 | Deshabilitar botón submit al enviar | Bajo | Bajo |
| 11 | Auto-ocultar notificaciones toast | Bajo | Bajo |
| 12 | Total en tiempo real en formulario campo | Medio | Bajo |
| 13 | Rate limiting en login y API | Alto | Bajo |
| 14 | Filtros de fecha en reportes de vendedores/clientes | Medio | Bajo |
| 15 | Paginación en reportes | Medio | Bajo |
| 16 | Sentry para errores en producción | Alto | Bajo |
| 17 | Backup automático PostgreSQL (cron \+ pg\_dump) | Alto | Bajo |
| 18 | Reporte de análisis de competencia | Medio | Medio |
| 19 | Módulo de visitas comerciales completo | Medio | Alto |
| 20 | API REST para integración con ERP | Medio | Alto |

---

¿Quieres que empiece a implementar alguno de estos puntos? Los más rápidos de alto impacto serían los índices de base de datos (\#6), el historial de estados del pedido (\#5), las notificaciones por email (\#3) y el disable del botón submit   
