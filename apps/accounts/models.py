from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    """Tenant — empresa cliente de SmartSales."""

    PLANES = [
        ('starter', 'Starter'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    name       = models.CharField('nombre', max_length=200)
    slug       = models.SlugField(unique=True, help_text='Identificador URL único. Ej: el-gran-chaparral')
    is_active  = models.BooleanField('activa', default=True)
    plan       = models.CharField(max_length=20, choices=PLANES, default='starter')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Organización'
        verbose_name_plural = 'Organizaciones'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def total_usuarios(self):
        return self.user_set.filter(is_active=True).count()


class User(AbstractUser):
    """Usuario del sistema con rol y organización."""

    ROLES = [
        ('superadmin', 'Super Admin'),
        ('gerente',    'Gerente'),
        ('supervisor', 'Supervisor'),
        ('vendedor',   'Vendedor'),
        ('facturador', 'Facturador'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='organización',
        help_text='Vacío solo para superadmins de SmartSales',
    )
    role = models.CharField('rol', max_length=20, choices=ROLES, default='vendedor')
    
    supervisor_asignado = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendedores_asignados',
        limit_choices_to={'role': 'supervisor'},
        verbose_name='supervisor asignado',
        help_text='Indica a qué supervisor rinde cuentas este vendedor.'
    )

    # Usar email como campo de login en lugar de username
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'

    @property
    def is_gerente(self):
        return self.role == 'gerente'

    @property
    def is_vendedor(self):
        return self.role == 'vendedor'

    @property
    def is_supervisor(self):
        return self.role == 'supervisor'

    @property
    def is_facturador(self):
        return self.role == 'facturador'

    @property
    def can_access_dashboard(self):
        """Todos menos el facturador pueden ver algún tipo de dashboard."""
        return self.role in ('superadmin', 'gerente', 'supervisor', 'vendedor')
