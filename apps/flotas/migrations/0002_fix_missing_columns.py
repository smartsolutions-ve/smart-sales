"""
Migración de corrección: ViajeDetalle.organization_id y ViajeDetalle.created_at.
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


def fix_viajedetalle_columns(apps, schema_editor):
    from django.db import connection
    vendor = connection.vendor

    with connection.cursor() as c:

        # ── organization_id ───────────────────────────────────────────────────
        if not _column_exists(c, vendor, 'flotas_viajedetalle', 'organization_id'):
            if vendor == 'sqlite':
                c.execute(
                    "ALTER TABLE flotas_viajedetalle ADD COLUMN organization_id integer"
                )
            else:
                c.execute(
                    "ALTER TABLE flotas_viajedetalle ADD COLUMN organization_id bigint"
                )
            # Poblar desde viaje.organization_id
            c.execute(
                "UPDATE flotas_viajedetalle SET organization_id = "
                "(SELECT organization_id FROM flotas_viaje WHERE id = viaje_id)"
            )
            if vendor != 'sqlite':
                c.execute(
                    "ALTER TABLE flotas_viajedetalle ALTER COLUMN organization_id SET NOT NULL"
                )
                c.execute(
                    "ALTER TABLE flotas_viajedetalle ADD CONSTRAINT "
                    "flotas_viajedetalle_organization_id_fk "
                    "FOREIGN KEY (organization_id) REFERENCES accounts_organization(id) "
                    "DEFERRABLE INITIALLY DEFERRED"
                )

        # ── created_at ────────────────────────────────────────────────────────
        if not _column_exists(c, vendor, 'flotas_viajedetalle', 'created_at'):
            if vendor == 'sqlite':
                c.execute(
                    "ALTER TABLE flotas_viajedetalle ADD COLUMN "
                    "created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP"
                )
            else:
                c.execute(
                    "ALTER TABLE flotas_viajedetalle ADD COLUMN "
                    "created_at timestamp with time zone NOT NULL DEFAULT NOW()"
                )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('flotas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            fix_viajedetalle_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
