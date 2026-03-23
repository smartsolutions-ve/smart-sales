from django.contrib import admin
from .models import ChatMensaje


@admin.register(ChatMensaje)
class ChatMensajeAdmin(admin.ModelAdmin):
    list_display = ['user', 'rol', 'organization', 'created_at']
    list_filter = ['rol', 'organization']
    search_fields = ['contenido', 'user__username']
    readonly_fields = ['created_at']
