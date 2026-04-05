#!/usr/bin/env bash
# build.sh — Script de build para Render.com
# Render ejecuta este script en cada deploy.
set -o errexit   # Salir si cualquier comando falla

echo "==> Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Recopilando archivos estaticos..."
python manage.py collectstatic --noinput

echo "==> Ejecutando migraciones..."
python manage.py migrate --noinput

echo "==> Creando superusuario (si no existe)..."
python manage.py createsuperuser --noinput || true

echo "==> Cargando datos de demo (si existen)..."
python manage.py loaddata fixtures/demo_data.json || true

echo "==> Cargando datos sintéticos de MegaConfites B2B..."
python manage.py load_megaconfites || true

echo "==> Build completado!"
