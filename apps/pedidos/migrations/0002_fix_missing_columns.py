"""
Migración de corrección: añade columnas que faltan en producción.

Causa raíz: el commit b217d08 (06-Apr-2026) recreó 0001_initial.py desde cero
consolidando 6 migraciones antiguas. La BD de producción ya tenía 0001 marcado
como aplicado, por lo que Django no volvió a ejecutarlo. Las columnas añadidas
en ese refactor nunca llegaron a la BD de Render.

Tablas afectadas:
- pedidos_pedidoitem   → organization_id, created_at, updated_at
- pedidos_pedidolog    → organization_id
- pedidos_factura      → organization_id
- pedidos_pedidoestadohistorial → organization_id
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


def _table_exists(cursor, vendor, table):
    if vendor == 'sqlite':
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=%s", [table]
        )
        return bool(cursor.fetchone())
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", [table]
    )
    return bool(cursor.fetchone())


def add_fk_column(cursor, vendor, table, column, ref_table, ref_column, source_sql):
    """Añade una columna FK NOT NULL usando SQL adecuado al vendor."""
    if vendor == 'sqlite':
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} integer")
    else:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} bigint")

    # Poblar desde tabla relacionada
    cursor.execute(f"UPDATE {table} SET {column} = ({source_sql})")

    if vendor != 'sqlite':
        cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")
        constraint = f"{table}_{column}_fk".replace('.', '_')
        cursor.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column}) "
            f"DEFERRABLE INITIALLY DEFERRED"
        )


def add_datetime_column(cursor, vendor, table, column):
    """Añade una columna datetime NOT NULL con default NOW para filas existentes."""
    if vendor == 'sqlite':
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} "
            f"datetime NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
    else:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} "
            f"timestamp with time zone NOT NULL DEFAULT NOW()"
        )


def fix_pedidos_columns(apps, schema_editor):
    from django.db import connection
    vendor = connection.vendor

    with connection.cursor() as c:

        # ── PedidoItem ────────────────────────────────────────────────────────
        if not _column_exists(c, vendor, 'pedidos_pedidoitem', 'organization_id'):
            add_fk_column(
                c, vendor,
                'pedidos_pedidoitem', 'organization_id',
                'accounts_organization', 'id',
                'SELECT organization_id FROM pedidos_pedido WHERE id = pedido_id',
            )

        if not _column_exists(c, vendor, 'pedidos_pedidoitem', 'created_at'):
            add_datetime_column(c, vendor, 'pedidos_pedidoitem', 'created_at')

        if not _column_exists(c, vendor, 'pedidos_pedidoitem', 'updated_at'):
            add_datetime_column(c, vendor, 'pedidos_pedidoitem', 'updated_at')

        # ── PedidoLog ─────────────────────────────────────────────────────────
        if _table_exists(c, vendor, 'pedidos_pedidolog'):
            if not _column_exists(c, vendor, 'pedidos_pedidolog', 'organization_id'):
                add_fk_column(
                    c, vendor,
                    'pedidos_pedidolog', 'organization_id',
                    'accounts_organization', 'id',
                    'SELECT organization_id FROM pedidos_pedido WHERE id = pedido_id',
                )

        # ── Factura ───────────────────────────────────────────────────────────
        if _table_exists(c, vendor, 'pedidos_factura'):
            if not _column_exists(c, vendor, 'pedidos_factura', 'organization_id'):
                add_fk_column(
                    c, vendor,
                    'pedidos_factura', 'organization_id',
                    'accounts_organization', 'id',
                    'SELECT organization_id FROM pedidos_pedido WHERE id = pedido_id',
                )

        # ── PedidoEstadoHistorial ─────────────────────────────────────────────
        if _table_exists(c, vendor, 'pedidos_pedidoestadohistorial'):
            if not _column_exists(c, vendor, 'pedidos_pedidoestadohistorial', 'organization_id'):
                add_fk_column(
                    c, vendor,
                    'pedidos_pedidoestadohistorial', 'organization_id',
                    'accounts_organization', 'id',
                    'SELECT organization_id FROM pedidos_pedido WHERE id = pedido_id',
                )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('pedidos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            fix_pedidos_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
