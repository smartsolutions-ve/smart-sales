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

echo "==> Cargando datos de El Gran Chaparral 2024 C.A...."
python manage.py setup_test_data --reset || true

echo "==> Organización demo con 24 meses de historia (solo la primera vez)..."
# Idempotente: si la org demo-historico ya existe no hace nada. Las claves de sus
# usuarios salen de la variable SEED_CREDENCIALES (no se imprimen en el log).
python manage.py seed_historico || true

echo "==> Build completado!"
