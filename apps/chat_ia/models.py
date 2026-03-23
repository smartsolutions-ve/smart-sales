from django.db import models
from django.conf import settings
from apps.pedidos.models import TenantModel


class ChatMensaje(TenantModel):
    """Mensaje del historial de conversación con la IA."""
    ROL_CHOICES = [
        ('user', 'Usuario'),
        ('assistant', 'Asistente'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_mensajes',
    )
    rol = models.CharField(max_length=10, choices=ROL_CHOICES)
    contenido = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensaje de Chat IA'
        verbose_name_plural = 'Mensajes de Chat IA'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['organization', 'user', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_rol_display()} — {self.created_at:%d/%m/%Y %H:%M}'
