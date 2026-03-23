"""Vistas del módulo Chat IA."""
import logging
from datetime import timedelta
from importlib import import_module
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings

from apps.accounts.decorators import role_required
from .models import ChatMensaje

logger = logging.getLogger('chat_ia')


def _get_backend():
    """Resuelve el backend de LLM desde settings.CHAT_IA_BACKEND."""
    path = settings.CHAT_IA_BACKEND
    module_path, class_name = path.rsplit('.', 1)
    return getattr(import_module(module_path), class_name)()


@login_required
@role_required('gerente', 'superadmin')
def ask_view(request):
    """Recibe una pregunta, consulta la IA y retorna los mensajes nuevos."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    pregunta = request.POST.get('pregunta', '').strip()

    if not pregunta:
        return JsonResponse({'error': 'La pregunta no puede estar vacía.'}, status=400)
    if len(pregunta) > 500:
        return JsonResponse({'error': 'Pregunta muy larga (máx 500 caracteres).'}, status=400)

    org = request.org
    if not org:
        if request.htmx:
            return HttpResponse(
                '<div class="text-center text-sm text-slate-500 py-4">'
                'El chat IA requiere una organización. '
                'Accede como gerente de una organización para usarlo.'
                '</div>'
            )
        return redirect('chat_ia:chat')

    # Rate limiting
    rate_limit = getattr(settings, 'CHAT_IA_RATE_LIMIT_HOUR', 30)
    hace_una_hora = timezone.now() - timedelta(hours=1)
    preguntas_recientes = ChatMensaje.objects.filter(
        organization=org,
        user=request.user,
        rol='user',
        created_at__gte=hace_una_hora,
    ).count()

    if preguntas_recientes >= rate_limit:
        msg_error = ChatMensaje.objects.create(
            organization=org,
            user=request.user,
            rol='assistant',
            contenido=f'Has alcanzado el límite de {rate_limit} consultas por hora. '
                      'Por favor espera unos minutos antes de continuar.',
        )
        if request.htmx:
            return render(request, 'chat_ia/_mensaje.html', {'mensajes': [msg_error]})
        return redirect('chat_ia:chat')

    # Guardar pregunta
    msg_user = ChatMensaje.objects.create(
        organization=org,
        user=request.user,
        rol='user',
        contenido=pregunta,
    )

    # Cargar historial (truncar respuestas largas para ahorrar tokens)
    n = getattr(settings, 'CHAT_IA_HISTORY_LENGTH', 10)
    historial_qs = (
        ChatMensaje.objects.filter(organization=org, user=request.user)
        .exclude(pk=msg_user.pk)
        .order_by('-created_at')[:n]
    )
    MAX_MSG_LEN = 500
    historial = []
    for m in reversed(list(historial_qs)):
        contenido = m.contenido
        if len(contenido) > MAX_MSG_LEN:
            contenido = contenido[:MAX_MSG_LEN] + '...'
        historial.append({'rol': m.rol, 'contenido': contenido})

    # Construir contexto y llamar al LLM
    try:
        from .services.context import build_context_for_org
        contexto = build_context_for_org(org)
        backend = _get_backend()
        respuesta_texto = backend.ask(
            pregunta=pregunta,
            historial=historial,
            contexto=contexto,
            org_name=org.name,
        )
    except Exception as e:
        logger.error('Chat IA error para org=%s user=%s: %s',
                     org.slug, request.user.username, e, exc_info=True)
        respuesta_texto = (
            'Lo siento, no pude procesar tu consulta en este momento. '
            'El servicio de IA no está disponible temporalmente. '
            'Por favor intenta de nuevo en unos segundos.'
        )

    # Guardar respuesta
    msg_assistant = ChatMensaje.objects.create(
        organization=org,
        user=request.user,
        rol='assistant',
        contenido=respuesta_texto,
    )

    if request.htmx:
        return render(request, 'chat_ia/_mensaje.html', {
            'mensajes': [msg_user, msg_assistant],
        })

    return redirect('chat_ia:chat')


@login_required
@role_required('gerente', 'superadmin')
def chat_view(request):
    """Página completa del historial de conversación."""
    if not request.org:
        mensajes = ChatMensaje.objects.none()
    else:
        mensajes = ChatMensaje.objects.filter(
            organization=request.org,
            user=request.user,
        ).order_by('created_at')[:50]

    # Si viene del chat flotante, retornar solo mensajes
    if request.GET.get('formato') == 'flotante':
        return render(request, 'chat_ia/_mensaje.html', {'mensajes': mensajes})

    return render(request, 'chat_ia/chat.html', {'mensajes': mensajes})
