# Deploy SmartSales Django — DigitalOcean

Basado en el proceso de despliegue documentado de Smart Solutions.
Droplet: Ubuntu 24.04 LTS, $6/mes (1GB RAM, 1 CPU, 25GB SSD).

---

## Requisitos previos

- Droplet de DigitalOcean ya creado (el existente de $6/mes)
- Dominio con DNS apuntando al droplet
- Cuenta en Resend.com para emails
- Repositorio GitHub del proyecto

---

## Fase 1: Configuración inicial del servidor

```bash
# Conectar al servidor
ssh root@TU_IP

# Actualizar sistema
apt update && apt upgrade -y

# Crear usuario deploy
adduser deploy
usermod -aG sudo deploy

# Configurar firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## Fase 2: Instalar Docker y Docker Compose

```bash
su - deploy

# Dependencias
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common git

# GPG key de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Repositorio
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verificar
docker --version && docker-compose --version
```

---

## Fase 3: Clonar el proyecto

```bash
cd ~
git clone https://github.com/smartsales-ve/smartsales-django.git smartsales

# Crear directorios necesarios (excluidos del repo por .gitignore)
mkdir -p ~/smartsales/postgres-data
mkdir -p ~/smartsales/nginx/conf.d
mkdir -p ~/smartsales/certbot/{conf,www}
mkdir -p ~/smartsales/staticfiles
mkdir -p ~/smartsales/media
```

---

## Fase 4: Variables de entorno

```bash
cd ~/smartsales
cp .env.example .env
nano .env
```

Editar con los valores reales:

```bash
# Generar SECRET_KEY segura:
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Pegar el resultado en SECRET_KEY=
SECRET_KEY=TU_CLAVE_SECRETA_AQUI
DEBUG=False
ALLOWED_HOSTS=tudominio.com,www.tudominio.com,TU_IP

DATABASE_URL=postgresql://smartsales:TU_CONTRASEÑA_DB@db:5432/smartsales
DB_NAME=smartsales
DB_USER=smartsales
DB_PASSWORD=TU_CONTRASEÑA_DB

RESEND_API_KEY=re_tu_api_key
DEFAULT_FROM_EMAIL=noreply@tudominio.com
DJANGO_SETTINGS_MODULE=config.settings.prod
```

```bash
# Proteger el archivo
chmod 600 .env
```

---

## Fase 5: Configurar Nginx

Editar los archivos Nginx con tu dominio real:

```bash
# Reemplazar "tudominio.com" con tu dominio real
sed -i 's/tudominio.com/tu-dominio-real.com/g' ~/smartsales/nginx/conf.d/smartsales.conf
```

**IMPORTANTE:** Usar la configuración HTTP (sin SSL) hasta obtener el certificado.
Edita el archivo y comenta el bloque HTTPS, deja solo el bloque HTTP que hace proxy al backend.

```bash
nano ~/smartsales/nginx/conf.d/smartsales.conf
```

---

## Fase 6: Primer deploy

```bash
cd ~/smartsales

# Construir imagen Django
docker-compose build web

# Levantar base de datos
docker-compose up -d db
sleep 5

# Levantar todo
docker-compose up -d

# Ver logs
docker-compose logs -f web
# Esperar: "Booting worker with pid..." → Django corriendo ✅
```

---

## Fase 7: Configurar superadmin y datos iniciales

```bash
# Crear superusuario de Django (SmartSales admin)
docker-compose exec web python manage.py createsuperuser
# Username: admin
# Email: tu@email.com
# Password: (elige una segura)

# Crear primera organización (El Gran Chaparral)
docker-compose exec web python manage.py shell
```

```python
from apps.accounts.models import Organization, User

# Crear organización
org = Organization.objects.create(
    name='El Gran Chaparral',
    slug='el-gran-chaparral',
    is_active=True,
    plan='starter',
)

# Crear gerente de la organización
gerente = User.objects.create_user(
    username='gerente.chaparral',
    email='gerente@chaparral.com',
    password='TU_CONTRASEÑA_SEGURA',
    first_name='Gerente',
    last_name='Chaparral',
    organization=org,
    role='gerente',
)

print(f"Org: {org} | Gerente: {gerente}")
exit()
```

---

## Fase 8: SSL con Let's Encrypt

```bash
# Verificar que el sitio responde en HTTP primero:
curl -I http://tudominio.com

# Obtener certificado
docker run -it --rm \
  -v ~/smartsales/certbot/conf:/etc/letsencrypt \
  -v ~/smartsales/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email tu@email.com \
  --agree-tos \
  --no-eff-email \
  -d tudominio.com \
  -d www.tudominio.com

# Si sale "Successfully received certificate" → activar HTTPS en nginx.conf
# (descomentar el bloque HTTPS)
docker-compose restart nginx
```

---

## Fase 9: Crons de mantenimiento

```bash
# Script de backup
nano ~/backup-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR=/home/deploy/backups
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)

cd /home/deploy/smartsales
docker-compose exec -T db pg_dump -U smartsales smartsales > $BACKUP_DIR/smartsales_$DATE.sql
gzip $BACKUP_DIR/smartsales_$DATE.sql

# Mantener solo los últimos 7 backups
ls -t $BACKUP_DIR/*.sql.gz | tail -n +8 | xargs rm -f

echo "Backup completado: smartsales_$DATE.sql.gz"
```

```bash
chmod +x ~/backup-db.sh

# Renovar SSL cada día a las 3am, backup a las 2am
crontab -e
# Agregar:
0 2 * * * /home/deploy/backup-db.sh >> /home/deploy/backup.log 2>&1
0 3 * * * docker run --rm -v /home/deploy/smartsales/certbot/conf:/etc/letsencrypt -v /home/deploy/smartsales/certbot/www:/var/www/certbot certbot/certbot renew && cd /home/deploy/smartsales && docker-compose restart nginx >> /home/deploy/ssl-renew.log 2>&1
```

---

## Proceso de deploy de actualizaciones

```bash
# 1. Desde tu computadora: commit y push
git add -p
git commit -m "descripción del cambio"
git push origin main

# 2. En el servidor: actualizar y reconstruir
ssh deploy@TU_IP
cd ~/smartsales
git pull origin main

# 3. Reconstruir imagen y reiniciar Django
docker-compose build web
docker-compose up -d --force-recreate web

# 4. Verificar
docker-compose logs -f web
# El proceso completo dura < 2 minutos
```

---

## Referencia rápida

```bash
# Ver estado
cd ~/smartsales && docker-compose ps

# Logs en tiempo real
docker-compose logs -f web       # Django
docker-compose logs -f nginx     # Nginx
docker-compose logs -f db        # PostgreSQL

# Comandos Django
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py shell
docker-compose exec web python manage.py createsuperuser

# Acceder a PostgreSQL
docker-compose exec db psql -U smartsales -d smartsales

# Reiniciar servicios
docker-compose restart web
docker-compose restart nginx

# Recursos
docker stats
```

---

## Checklist de producción

- [ ] El sitio carga en `https://tudominio.com`
- [ ] Redirige HTTP → HTTPS
- [ ] CSS/JS se ven correctamente
- [ ] Login funciona con el gerente de prueba
- [ ] El formulario de campo funciona en Android
- [ ] Backup automático configurado (cron)
- [ ] SSL automático configurado (cron)
- [ ] `DEBUG=False` en el `.env`
- [ ] `SECRET_KEY` única y segura
- [ ] `.env` tiene permisos `600`
