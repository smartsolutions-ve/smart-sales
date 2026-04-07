import datetime
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TasaCambio',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tasa', models.DecimalField(decimal_places=4, help_text='1 USD = X Bs. Ej: 36.50', max_digits=12, verbose_name='Tasa USD/Bs')),
                ('fecha', models.DateField(default=datetime.date.today, verbose_name='Fecha de vigencia')),
                ('activa', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasas_cambio', to='accounts.organization')),
            ],
            options={
                'verbose_name': 'Tasa de cambio',
                'verbose_name_plural': 'Tasas de cambio',
                'ordering': ['-fecha', '-created_at'],
            },
        ),
    ]
