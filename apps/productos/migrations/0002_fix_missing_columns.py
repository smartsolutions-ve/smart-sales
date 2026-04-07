"""
Migración de corrección: Lote.organization_id y MovimientoInventario.organization_id.
Mismo origen que pedidos/0002_fix_missing_columns.py (refactor b217d08).
"""
from django.db import migrations


def _column_exists(cursor, vendor, table, column):
    if vendor == 'sqlite':
        cursor.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cursor.fetchall())
    cursor.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        [table, column],
    )
    return bool(cursor.fetchone())


def fix_lote_movimiento_columns(apps, schema_editor):
    from django.db import connection
    vendor = connection.vendor

    with connection.cursor() as c:

        # ── Lote.organization_id ──────────────────────────────────────────────
        if not _column_exists(c, vendor, 'productos_lote', 'organization_id'):
            if vendor == 'sqlite':
                c.execute(
                    "ALTER TABLE productos_lote ADD COLUMN organization_id integer"
                )
            else:
                c.execute(
                    "ALTER TABLE productos_lote ADD COLUMN organization_id bigint"
                )
            # Poblar desde producto.organization_id
            c.execute(
                "UPDATE productos_lote SET organization_id = "
                "(SELECT organization_id FROM productos_producto WHERE id = producto_id)"
            )
            if vendor != 'sqlite':
                c.execute(
                    "ALTER TABLE productos_lote ALTER COLUMN organization_id SET NOT NULL"
                )
                c.execute(
                    "ALTER TABLE productos_lote ADD CONSTRAINT "
                    "productos_lote_organization_id_fk "
                    "FOREIGN KEY (organization_id) REFERENCES accounts_organization(id) "
                    "DEFERRABLE INITIALLY DEFERRED"
                )

        # ── MovimientoInventario.organization_id ──────────────────────────────
        if not _column_exists(c, vendor, 'productos_movimientoinventario', 'organization_id'):
            if vendor == 'sqlite':
                c.execute(
                    "ALTER TABLE productos_movimientoinventario ADD COLUMN organization_id integer"
                )
            else:
                c.execute(
                    "ALTER TABLE productos_movimientoinventario ADD COLUMN organization_id bigint"
                )
            # Poblar desde lote.producto.organization_id
            c.execute(
                "UPDATE productos_movimientoinventario SET organization_id = ("
                "  SELECT p.organization_id "
                "  FROM productos_lote l "
                "  JOIN productos_producto p ON l.producto_id = p.id "
                "  WHERE l.id = lote_id"
                ")"
            )
            if vendor != 'sqlite':
                c.execute(
                    "ALTER TABLE productos_movimientoinventario "
                    "ALTER COLUMN organization_id SET NOT NULL"
                )
                c.execute(
                    "ALTER TABLE productos_movimientoinventario ADD CONSTRAINT "
                    "productos_movimientoinventario_organization_id_fk "
                    "FOREIGN KEY (organization_id) REFERENCES accounts_organization(id) "
                    "DEFERRABLE INITIALLY DEFERRED"
                )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('productos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            fix_lote_movimiento_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
