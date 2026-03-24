# Guias de Deploy — SmartSales

---

# PARTE 1: Render.com (Demo gratuito para el cliente)

**Objetivo:** Tener SmartSales funcionando en una URL publica (ej. `smartsales-xxxx.onrender.com`) para que el cliente lo pruebe. **100% gratuito**, incluyendo Chat IA y PostgreSQL.

**Tiempo estimado:** 20-30 minutos

**Por que Render y no PythonAnywhere:** PythonAnywhere gratuito bloquea conexiones HTTP salientes a dominios no whitelisted (`generativelanguage.googleapis.com`, `openrouter.ai`), lo cual rompe el Chat IA. Render.com no tiene esta restriccion.

---

## 1.1 Prerequisitos

Antes de empezar, asegurate de tener:

1. **El proyecto subido a GitHub** (repositorio publico o privado)
2. **Tus API keys a la mano:**
   - `GEMINI_API_KEY` (de Google AI Studio)
   - `OPENROUTER_API_KEY` (de openrouter.ai)

Si no has subido a GitHub aun:

```bash
# En tu maquina local, dentro de la carpeta del proyecto
git add -A
git commit -m "Preparar para deploy en Render"
git push origin main
```

---

## 1.2 Crear cuenta en Render.com

1. Ir a [render.com](https://render.com/)
2. Click en **Get Started for Free**
3. **Registrarse con GitHub** (recomendado — simplifica conectar tu repositorio)
4. Confirmar tu email si te lo pide

---

## 1.3 Verificar archivos necesarios en tu proyecto

Tu proyecto ya tiene estos 3 archivos listos para Render. Verificalos:

### `build.sh` (en la raiz del proyecto)

```bash
#!/usr/bin/env bash
set -o errexit
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
```

> **IMPORTANTE:** Este archivo debe tener permisos de ejecucion. Si no los tiene:
> ```bash
> chmod +x build.sh
> git add build.sh
> git commit -m "Hacer build.sh ejecutable"
> git push origin main
> ```

### `config/settings/render.py`

Este archivo ya existe en el proyecto. Contiene la configuracion especifica para Render:
- HTTPS via proxy (Render termina SSL)
- WhiteNoise para archivos estaticos
- PostgreSQL via `DATABASE_URL`
- Email en modo consola (no envia en demo)

### `render.yaml` (en la raiz — opcional, para deploy automatico)

Define la infraestructura como codigo. Render lo detecta automaticamente.

---

## 1.4 Crear la base de datos PostgreSQL

1. En el dashboard de Render, click en **New** → **PostgreSQL**
2. Configurar:

| Campo | Valor |
|-------|-------|
| Name | `smartsales-db` |
| Database | `smartsales` |
| User | `smartsales` |
| Region | **Oregon (US West)** (o la que prefieras) |
| Plan | **Free** |

3. Click en **Create Database**
4. Esperar ~1-2 minutos a que se cree

> **Nota:** El plan gratuito de PostgreSQL en Render **expira despues de 90 dias**. Despues de ese periodo, necesitaras crear una nueva BD o migrar a un plan pago ($7/mes). Para una demo esto es mas que suficiente.

5. Una vez creada, ir a la seccion **Info** de la base de datos
6. **Copiar el valor de "Internal Database URL"** — lo necesitaras en el paso 1.6. Se ve asi:
   ```
   postgresql://smartsales:XXXXXXXXXX@dpg-xxxxx-a.oregon-postgres.render.com/smartsales
   ```

---

## 1.5 Crear el Web Service

1. En el dashboard de Render, click en **New** → **Web Service**
2. Seleccionar **Build and deploy from a Git repository** → **Next**
3. Conectar tu cuenta de GitHub (si no lo hiciste al registrarte):
   - Click en **Connect account**
   - Autorizar Render
   - Seleccionar el repositorio `smart-sales`
4. Configurar el servicio:

| Campo | Valor |
|-------|-------|
| **Name** | `smartsales` (sera tu URL: `smartsales.onrender.com`) |
| **Region** | La misma region que la base de datos |
| **Branch** | `main` |
| **Runtime** | **Python 3** |
| **Build Command** | `./build.sh` |
| **Start Command** | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
| **Plan** | **Free** |

> **MUY IMPORTANTE:** El campo **Start Command** debe ser exactamente como esta arriba. `$PORT` es una variable que Render inyecta automaticamente — NO la reemplaces con un numero.

5. **NO** hagas click en "Create Web Service" todavia — primero configura las variables de entorno (paso 1.6)

---

## 1.6 Configurar variables de entorno

En la misma pagina de creacion del Web Service, baja a la seccion **Environment Variables** y agrega estas variables **una por una**:

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.12.3` |
| `DJANGO_SETTINGS_MODULE` | `config.settings.render` |
| `SECRET_KEY` | *(click en "Generate" para auto-generar)* |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` |
| `DATABASE_URL` | *(pegar el "Internal Database URL" copiado en paso 1.4)* |
| `GEMINI_API_KEY` | *(tu clave de Google AI Studio)* |
| `OPENROUTER_API_KEY` | *(tu clave de OpenRouter)* |
| `OPENROUTER_MODEL` | `google/gemma-3-27b-it:free` |
| `CHAT_IA_BACKEND` | `apps.chat_ia.services.gemini.GeminiBackend` |
| `DEFAULT_FROM_EMAIL` | `noreply@smartsales.com.ve` |
| `RESEND_API_KEY` | `re_placeholder` |

### Detalles importantes sobre cada variable:

- **`PYTHON_VERSION`**: Render usa Python 3.7 por defecto si no lo especificas. **Debes** poner `3.12.3`.
- **`DJANGO_SETTINGS_MODULE`**: Debe ser `config.settings.render` (NO `dev` ni `prod`).
- **`SECRET_KEY`**: Render tiene un boton "Generate" que crea un valor aleatorio seguro. Usalo.
- **`DATABASE_URL`**: Es la **Internal Database URL** (empieza con `postgresql://`), NO la External. La Internal es mas rapida porque la conexion es dentro de la red de Render.
- **`GEMINI_API_KEY`**: Tu clave de [Google AI Studio](https://aistudio.google.com/apikey). Empieza con `AIza...`.
- **`OPENROUTER_API_KEY`**: Tu clave de [OpenRouter](https://openrouter.ai/keys). Empieza con `sk-or-...`.
- **`CHAT_IA_BACKEND`**: Si prefieres usar OpenRouter en vez de Gemini, cambia a `apps.chat_ia.services.openrouter.OpenRouterBackend`.

---

## 1.7 Crear el servicio (Deploy)

1. Verifica que todas las variables de entorno estan correctas
2. Click en **Create Web Service**
3. Render empezara el build automaticamente. Veras el log en tiempo real:
   - Clonar repositorio...
   - Instalar dependencias (`pip install`)...
   - `collectstatic`...
   - `migrate`...
   - Iniciar gunicorn...
4. **El primer deploy tarda 3-5 minutos.** Espera a que diga "Your service is live"

> **Si el build falla:** Lee el log de error. Los problemas mas comunes son:
> - **`ModuleNotFoundError`**: Falta una dependencia en `requirements.txt`
> - **WeasyPrint falla**: Render no tiene las librerias del sistema para WeasyPrint. Ver seccion 1.10 para solucionarlo
> - **`SECRET_KEY` missing**: No configuraste la variable de entorno

---

## 1.8 Crear el superusuario

Render no tiene consola SSH persistente como PythonAnywhere, pero puedes ejecutar comandos desde la seccion **Shell** del servicio:

1. Ir a tu Web Service en Render → pestaña **Shell**
2. Ejecutar:

```bash
python manage.py createsuperuser
```

3. Seguir las instrucciones (username, email, password)

> **Alternativa:** Si la Shell no esta disponible en plan gratuito, puedes crear un management command temporal. Agrega esta variable de entorno en Render:
>
> | Key | Value |
> |-----|-------|
> | `DJANGO_SUPERUSER_USERNAME` | `admin` |
> | `DJANGO_SUPERUSER_EMAIL` | `admin@smartsales.com.ve` |
> | `DJANGO_SUPERUSER_PASSWORD` | `TuPasswordSeguro123!` |
>
> Y agrega esta linea al final de `build.sh` (antes del echo final):
> ```bash
> python manage.py createsuperuser --noinput || true
> ```
> Despues del primer deploy exitoso, **elimina** esas 3 variables de entorno y la linea del build.sh por seguridad.

---

## 1.9 Probar la aplicacion

1. Tu URL sera: `https://smartsales.onrender.com` (o el nombre que elegiste)
2. Ir a esa URL → deberia mostrar la pagina de login
3. Login con el superusuario que creaste
4. Probar:
   - [ ] Login funciona
   - [ ] Dashboard carga correctamente
   - [ ] Tablas tienen busqueda y ordenamiento (DataTables)
   - [ ] **Chat IA responde** (esta es la razon de usar Render)
   - [ ] Crear un pedido funciona
   - [ ] Modo oscuro funciona
   - [ ] Responsive en celular

> **Cold start:** El plan gratuito de Render apaga la app despues de 15 minutos de inactividad. La primera visita despues de estar inactiva tarda **30-60 segundos** en cargar. Esto es normal. Dile al cliente que espere unos segundos si la pagina tarda en cargar la primera vez.

---

## 1.10 Troubleshooting Render

### WeasyPrint falla en el build

Render (sin Docker) no tiene las librerias del sistema que WeasyPrint necesita (`pango`, `cairo`, etc.). Para solucionarlo tienes dos opciones:

**Opcion A (recomendada para demo):** Ignorar WeasyPrint. Los PDFs no se generaran, pero el resto funciona perfecto. Crea un archivo `requirements-render.txt`:

```
# Mismas dependencias que requirements.txt pero sin WeasyPrint
-r requirements.txt
```

Y en tu `build.sh`, antes del `pip install`, agrega:
```bash
# Quitar WeasyPrint si causa problemas (PDFs no funcionaran)
sed -i 's/^weasyprint/#weasyprint/' requirements.txt
```

**Opcion B:** Usar Docker en Render (plan pago). Render soporta deploys con Dockerfile, que ya tiene las dependencias del sistema.

### Error "Internal Server Error" (500)

1. Ir a tu Web Service → pestaña **Logs**
2. Buscar el error especifico (traceback de Python)
3. Problemas comunes:
   - `OperationalError: connection refused` → La DATABASE_URL es incorrecta. Asegurate de usar la **Internal** URL
   - `DisallowedHost` → Falta `.onrender.com` en ALLOWED_HOSTS
   - `CSRF verification failed` → Falta `https://*.onrender.com` en CSRF_TRUSTED_ORIGINS

### La pagina no carga (error de Render, no de Django)

- Verificar que el **Start Command** es correcto
- Verificar que `gunicorn` esta en `requirements.txt` (si — ya esta)
- Ver los logs del servicio

### Los archivos estaticos no cargan (CSS, JS)

- Verificar que `whitenoise` esta en `requirements.txt` y en `MIDDLEWARE` (base.py ya lo tiene)
- Verificar que `collectstatic` se ejecuto sin errores en el build log

### La base de datos se resetea

Si usas SQLite (sin DATABASE_URL), el filesystem de Render es **efimero** — se borra en cada deploy. **Siempre** usa PostgreSQL (paso 1.4).

### Chat IA no funciona

1. Verificar que `GEMINI_API_KEY` esta configurada en las variables de entorno
2. Verificar que `CHAT_IA_BACKEND` apunta al backend correcto
3. En los logs, buscar errores de `google.generativeai` o `openai`
4. Si Gemini falla, cambiar `CHAT_IA_BACKEND` a `apps.chat_ia.services.openrouter.OpenRouterBackend`

---

## 1.11 Actualizar el demo despues de cambios

Render hace **auto-deploy** cada vez que haces push a `main` en GitHub:

```bash
# En tu maquina local
git add -A
git commit -m "Cambios para el demo"
git push origin main
```

Render detecta el push y automaticamente:
1. Clona el nuevo codigo
2. Ejecuta `build.sh` (instalar deps + collectstatic + migrate)
3. Reinicia gunicorn

Puedes ver el progreso en la pestaña **Events** de tu servicio.

> **Para desactivar auto-deploy:** En Settings del servicio → Auto-Deploy → "No". Asi puedes hacer push sin que se despliegue automaticamente, y hacer deploy manual desde el dashboard.

---

## 1.12 Cargar datos de demo (opcional)

Si quieres que el demo tenga datos pre-cargados:

### Opcion A: Crear un fixture desde tu maquina local

```bash
# En tu maquina local, exportar datos
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > fixtures/demo_data.json

# Subir a GitHub
git add fixtures/demo_data.json
git commit -m "Agregar datos de demo"
git push origin main
```

Luego en la Shell de Render:
```bash
python manage.py loaddata fixtures/demo_data.json
```

### Opcion B: Agregar loaddata al build.sh

Si quieres que los datos se carguen automaticamente en cada deploy, agrega al final de `build.sh`:
```bash
python manage.py loaddata fixtures/demo_data.json || true
```

---

## 1.13 Limites del plan gratuito de Render

| Limite | Valor |
|--------|-------|
| **Horas de instancia** | 750 horas/mes (suficiente para 1 servicio 24/7) |
| **Spin-down** | Se apaga despues de 15 min de inactividad |
| **Cold start** | 30-60 segundos para despertar |
| **RAM** | 512 MB |
| **PostgreSQL gratis** | 90 dias, 1 GB almacenamiento, 97 conexiones |
| **Ancho de banda** | 100 GB/mes |
| **Build time** | 500 min/mes |
| **HTTPS** | Automatico e incluido |
| **Conexiones salientes** | **Sin restricciones** (Chat IA funciona) |

> Para la demo con el cliente, estos limites son mas que suficientes.

---

---

# PARTE 2: DigitalOcean (Produccion)

**Objetivo:** Desplegar SmartSales en produccion con Docker, PostgreSQL, Nginx, SSL y dominio propio.

**Costo:** ~$6-12/mes (Droplet $6 + dominio ~$12/año)

**Tiempo estimado:** 1-2 horas

---

## 2.1 Prerequisitos

- Cuenta en [DigitalOcean](https://www.digitalocean.com/)
- Un dominio comprado (ej. `smartsales.app`, `smartsales.com.ve`)
- El proyecto en un repositorio Git (GitHub/GitLab)

---

## 2.2 Crear el Droplet

1. **Create Droplet**
2. Configuracion recomendada:

| Parametro | Valor |
|-----------|-------|
| Image | **Ubuntu 24.04 LTS** |
| Plan | **Basic $6/mes** (1 vCPU, 1GB RAM, 25GB SSD) |
| Region | **NYC1** o la mas cercana a Venezuela |
| Authentication | **SSH Key** (recomendado) o Password |
| Hostname | `smartsales-prod` |

3. Copiar la IP publica del droplet (ej. `164.92.xxx.xxx`)

---

## 2.3 Apuntar el dominio

En tu registrador de dominio, crear registros DNS:

| Tipo | Nombre | Valor |
|------|--------|-------|
| A | `@` | `164.92.xxx.xxx` |
| A | `www` | `164.92.xxx.xxx` |

> La propagacion DNS puede tardar hasta 48h, pero generalmente son 5-30 minutos.

---

## 2.4 Configurar el servidor

Conectarse por SSH:

```bash
ssh root@164.92.xxx.xxx
```

### Actualizar el sistema:

```bash
apt update && apt upgrade -y
```

### Instalar Docker y Docker Compose:

```bash
# Docker oficial
curl -fsSL https://get.docker.com | sh

# Docker Compose (ya viene incluido en Docker moderno)
docker compose version  # Verificar que funciona
```

### Crear usuario no-root (buena practica):

```bash
adduser deploy
usermod -aG docker deploy
usermod -aG sudo deploy

# Copiar la SSH key al nuevo usuario
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

A partir de aqui, conectarse como `deploy`:

```bash
ssh deploy@164.92.xxx.xxx
```

### Instalar dependencias adicionales:

```bash
sudo apt install -y git
```

---

## 2.5 Clonar el proyecto

```bash
cd ~
git clone https://github.com/TU_USUARIO/smart-sales.git
cd smart-sales
```

---

## 2.6 Configurar variables de entorno para produccion

```bash
nano .env
```

```env
# ── Django ──────────────────────────────────────
SECRET_KEY=una-clave-super-secreta-y-larga-generada-aleatoriamente
DEBUG=False
ALLOWED_HOSTS=tudominio.com,www.tudominio.com

# ── Base de datos ───────────────────────────────
DATABASE_URL=postgresql://smartsales:TU_PASSWORD_SEGURO@db:5432/smartsales
DB_NAME=smartsales
DB_USER=smartsales
DB_PASSWORD=TU_PASSWORD_SEGURO

# ── Email ──────────────────────────────────────
RESEND_API_KEY=re_tu_api_key_real_de_resend
DEFAULT_FROM_EMAIL=noreply@tudominio.com

# ── Chat IA ───────────────────────────────────
GEMINI_API_KEY=tu_clave_gemini
OPENROUTER_API_KEY=tu_clave_openrouter
OPENROUTER_MODEL=google/gemma-3-27b-it:free
CHAT_IA_BACKEND=apps.chat_ia.services.gemini.GeminiBackend

# ── CSRF ──────────────────────────────────────
CSRF_TRUSTED_ORIGINS=https://tudominio.com,https://www.tudominio.com

# ── Django settings module ────────────────────
DJANGO_SETTINGS_MODULE=config.settings.prod
```

Para generar la SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## 2.7 Configurar Nginx

Editar el archivo de configuracion de Nginx con tu dominio real:

```bash
nano nginx/conf.d/smartsales.conf
```

Reemplazar todas las ocurrencias de `tudominio.com` con tu dominio real.

---

## 2.8 Obtener certificado SSL (HTTPS)

Antes de levantar todo con HTTPS, necesitas el certificado. Hacemos un deploy temporal solo HTTP primero:

### Paso 1: Crear configuracion Nginx temporal (solo HTTP):

```bash
cat > nginx/conf.d/smartsales.conf << 'NGINX'
server {
    listen 80;
    server_name tudominio.com www.tudominio.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 20M;
}
NGINX
```

> **IMPORTANTE:** Reemplaza `tudominio.com` con tu dominio real en el archivo.

### Paso 2: Desactivar temporalmente HTTPS en settings

En `config/settings/prod.py`, temporalmente comentar o cambiar:

```python
SECURE_SSL_REDIRECT = False   # Cambiar de True a False temporalmente
```

### Paso 3: Levantar los servicios:

```bash
docker compose up -d --build
```

Verificar que funciona visitando `http://tudominio.com`

### Paso 4: Obtener el certificado SSL con Certbot:

```bash
# Crear directorios para certbot
mkdir -p certbot/conf certbot/www

# Ejecutar certbot via Docker
docker run --rm \
  -v $(pwd)/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d tudominio.com -d www.tudominio.com \
  --email tu@email.com \
  --agree-tos \
  --no-eff-email
```

### Paso 5: Restaurar la configuracion HTTPS de Nginx:

```bash
nano nginx/conf.d/smartsales.conf
```

Restaurar el contenido completo con HTTP→HTTPS redirect y el bloque SSL (el archivo original que ya tienes en el repo). **Reemplazar `tudominio.com`** con tu dominio real.

### Paso 6: Restaurar SECURE_SSL_REDIRECT:

```python
SECURE_SSL_REDIRECT = True   # Volver a True
```

### Paso 7: Rebuild y reiniciar:

```bash
docker compose down
docker compose up -d --build
```

Verificar que `https://tudominio.com` funciona con candado verde.

---

## 2.9 Migrar base de datos y crear superusuario

```bash
# Ejecutar migraciones
docker compose exec web python manage.py migrate

# Crear superusuario
docker compose exec web python manage.py createsuperuser
```

---

## 2.10 Cargar datos iniciales (opcional)

Si tienes un fixture de datos de demo:

```bash
docker compose exec web python manage.py loaddata fixtures/demo_data.json
```

O si quieres migrar datos desde SQLite (tu DB local):

```bash
# En tu maquina local, exportar datos
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > data_export.json

# Subir al servidor
scp data_export.json deploy@164.92.xxx.xxx:~/smart-sales/

# En el servidor, importar
docker compose exec web python manage.py loaddata data_export.json
```

---

## 2.11 Renovacion automatica de SSL

Crear un cron job para renovar el certificado:

```bash
crontab -e
```

Agregar:

```cron
0 3 1 * * cd /home/deploy/smart-sales && docker run --rm -v $(pwd)/certbot/conf:/etc/letsencrypt -v $(pwd)/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker compose exec nginx nginx -s reload
```

Esto renueva el certificado el dia 1 de cada mes a las 3 AM.

---

## 2.12 Configurar firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 2.13 Configurar swap (importante para 1GB RAM)

El droplet de $6 solo tiene 1GB de RAM. Docker + PostgreSQL + Django pueden necesitar mas:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Hacer permanente
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 2.14 Verificacion final

Checklist de verificacion:

- [ ] `https://tudominio.com` carga sin errores
- [ ] Login funciona
- [ ] Dashboard muestra graficas
- [ ] Crear pedido funciona
- [ ] Chat IA responde preguntas
- [ ] Modo oscuro funciona sin flash blanco
- [ ] Tablas tienen busqueda/ordenamiento (DataTables)
- [ ] Responsive: probar en celular
- [ ] Email de reset de contrasena funciona (si Resend esta configurado)
- [ ] PDFs se generan correctamente

---

## 2.15 Comandos utiles en produccion

```bash
# Ver logs en tiempo real
docker compose logs -f web

# Ver logs de Nginx
docker compose logs -f nginx

# Reiniciar todo
docker compose restart

# Rebuild despues de cambios
docker compose down
docker compose up -d --build

# Acceder a la shell de Django
docker compose exec web python manage.py shell

# Backup de la base de datos
docker compose exec db pg_dump -U smartsales smartsales > backup_$(date +%Y%m%d).sql

# Restaurar backup
cat backup_20260324.sql | docker compose exec -T db psql -U smartsales smartsales

# Limpiar chat IA viejo (mas de 90 dias)
docker compose exec web python manage.py limpiar_chat

# Ver uso de disco de Docker
docker system df
```

---

## 2.16 Actualizar en produccion (deploy de cambios)

```bash
cd ~/smart-sales

# Bajar cambios
git pull origin main

# Rebuild y reiniciar
docker compose down
docker compose up -d --build

# Migraciones (si hay)
docker compose exec web python manage.py migrate
```

Para **zero-downtime** (opcional, avanzado):
```bash
docker compose up -d --build --no-deps web
docker compose exec web python manage.py migrate
```

---

## 2.17 Monitoreo basico

### Opcion 1: UptimeRobot (gratis)
- Registrarse en [uptimerobot.com](https://uptimerobot.com/)
- Crear monitor HTTP(s) apuntando a `https://tudominio.com`
- Te notifica por email si el sitio se cae

### Opcion 2: Health check en el servidor

```bash
# Crear script de health check
cat > ~/healthcheck.sh << 'EOF'
#!/bin/bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://tudominio.com/login/)
if [ "$STATUS" != "200" ]; then
    echo "SmartSales DOWN! Status: $STATUS" | mail -s "ALERTA SmartSales" tu@email.com
    cd ~/smart-sales && docker compose restart
fi
EOF
chmod +x ~/healthcheck.sh

# Agregar a crontab (cada 5 minutos)
crontab -e
# Agregar: */5 * * * * /home/deploy/healthcheck.sh
```

---

# Resumen de diferencias

| Aspecto | Render.com (Demo) | DigitalOcean (Produccion) |
|---------|-------------------|---------------------------|
| **Uso** | Demo/staging para el cliente | Produccion final |
| **Costo** | Gratis | ~$6/mes + dominio |
| **DB** | PostgreSQL gratis (90 dias) | PostgreSQL (Docker, permanente) |
| **HTTPS** | Automatico e incluido | Let's Encrypt (configurar manualmente) |
| **Chat IA** | **Funciona completo** | Funciona completo |
| **Performance** | Limitada (512MB RAM, cold start) | Dedicada (1GB+ RAM, siempre activo) |
| **PDFs** | Puede fallar (sin librerias del sistema) | Funciona (Docker tiene todas las deps) |
| **Dominio** | smartsales.onrender.com | Tu dominio propio |
| **Deploy** | Auto-deploy al hacer git push | Manual (docker compose) |
| **Escalabilidad** | Limitada | Si (resize droplet) |
| **Control** | Limitado (PaaS) | Total (root access) |
