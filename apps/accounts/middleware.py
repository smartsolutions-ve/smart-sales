from django.shortcuts import redirect
from django.contrib import messages

RUTAS_PUBLICAS = ['/login/', '/logout/', '/static/', '/media/', '/__debug__/']


class TenantMiddleware:
    """
    Inyecta request.org con la organización del usuario logueado.
    Si la organización está inactiva, redirige con mensaje de error.
    El superadmin no tiene organización (request.org = None).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org = None  # Default

        # Saltar para rutas públicas y usuarios no autenticados
        if not request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(ruta) for ruta in RUTAS_PUBLICAS):
            return self.get_response(request)

        user = request.user

        # Superadmin (rol app) o superusuario Django: acceso global, sin organización
        if user.is_superadmin or user.is_superuser:
            return self.get_response(request)

        # Usuario sin organización asignada (error de configuración)
        if not user.organization:
            messages.error(request, 'Tu cuenta no tiene organización asignada. Contacta al administrador.')
            return redirect('accounts:login')

        # Organización inactiva
        if not user.organization.is_active:
            messages.warning(
                request,
                f'La cuenta de {user.organization.name} está suspendida. '
                'Contacta a SmartSales para reactivarla.'
            )
            return redirect('accounts:cuenta_suspendida')

        request.org = user.organization
        return self.get_response(request)
