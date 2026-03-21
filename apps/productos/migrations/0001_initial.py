import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoriaProducto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, verbose_name='nombre')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='accounts.organization', verbose_name='organización')),
            ],
            options={
                'verbose_name': 'Categoría',
                'verbose_name_plural': 'Categorías',
                'ordering': ['nombre'],
                'unique_together': {('organization', 'nombre')},
            },
        ),
        migrations.CreateModel(
            name='Producto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, verbose_name='nombre')),
                ('sku', models.CharField(blank=True, help_text='', max_length=50, verbose_name='SKU / Código')),
                ('descripcion', models.TextField(blank=True, verbose_name='descripción')),
                ('precio_base', models.DecimalField(blank=True, decimal_places=2, help_text='Precio sugerido de venta. Puede modificarse en cada pedido.', max_digits=12, null=True, verbose_name='precio base')),
                ('unidad', models.CharField(blank=True, help_text='Ej: unidad, kg, litro, caja', max_length=30, verbose_name='unidad de medida')),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('categoria', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='productos', to='productos.categoriaproducto', verbose_name='categoría')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='accounts.organization', verbose_name='organización')),
            ],
            options={
                'verbose_name': 'Producto',
                'verbose_name_plural': 'Productos',
                'ordering': ['nombre'],
                'unique_together': {('organization', 'sku')},
            },
        ),
    ]
