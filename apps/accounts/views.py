from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.views.decorators.http import require_http_methods

# Rate limiting constants for login
LOGIN_MAX_ATTEMPTS = 5
LOGIN_COOLDOWN_SECONDS = 15 * 60  # 15 minutes


def _get_login_attempt_cache_key(username):
    """Return cache key for tracking failed login attempts by username."""
    return f'login_attempts:{username.lower()}'


@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Login con email (como username) y contraseña."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Rate limiting: check failed attempts
        cache_key = _get_login_attempt_cache_key(username)
        attempts = cache.get(cache_key, 0)
        if attempts >= LOGIN_MAX_ATTEMPTS:
            messages.error(
                request,
                'Demasiados intentos fallidos. Por favor espera 15 minutos antes de intentar de nuevo.',
            )
            return render(request, 'accounts/login.html', {'username': username})

        user = authenticate(request, username=username, password=password)

        if user is None:
            # Increment failed attempts counter
            cache.set(cache_key, attempts + 1, LOGIN_COOLDOWN_SECONDS)
            messages.error(request, 'Usuario o contraseña incorrectos.')
            return render(request, 'accounts/login.html', {'username': username})

        if not user.is_active:
            messages.error(request, 'Esta cuenta está desactivada.')
            return render(request, 'accounts/login.html', {'username': username})

        # Verificar organización activa (para no-superadmin)
        if not user.is_superadmin and user.organization and not user.organization.is_active:
            messages.warning(
                request,
                f'La cuenta de {user.organization.name} está suspendida. '
                'Contacta a SmartSales para más información.'
            )
            return render(request, 'accounts/login.html', {'username': username})

        # Clear failed attempts on successful login
        cache.delete(cache_key)
        login(request, user)
        return _redirect_by_role(user)

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def cuenta_suspendida(request):
    return render(request, 'accounts/cuenta_suspendida.html')


@login_required
@require_http_methods(['GET', 'POST'])
def perfil(request):
    """Perfil del usuario: cambiar nombre y contraseña."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'datos':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save(update_fields=['first_name', 'last_name', 'email'])
            messages.success(request, 'Datos actualizados correctamente.')

        elif action == 'password':
            current = request.POST.get('current_password', '')
            new1 = request.POST.get('new_password', '')
            new2 = request.POST.get('new_password2', '')

            if not request.user.check_password(current):
                messages.error(request, 'La contraseña actual es incorrecta.')
            elif len(new1) < 8:
                messages.error(request, 'La nueva contraseña debe tener al menos 8 caracteres.')
            elif new1 != new2:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
            else:
                request.user.set_password(new1)
                request.user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Contraseña cambiada correctamente.')

        return redirect('accounts:perfil')

    return render(request, 'accounts/perfil.html')


def _redirect_by_role(user):
    """Redirige al usuario según su rol."""
    # Superadmin por rol de app O superusuario Django (creado con createsuperuser)
    if user.is_superadmin or user.is_superuser:
        return redirect('admin_panel:index')
    if user.is_gerente:
        return redirect('dashboard:index')
    # Vendedor
    return redirect('campo:index')
