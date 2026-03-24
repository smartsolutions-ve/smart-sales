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

echo "==> Build completado!"
