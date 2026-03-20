from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods


@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Login con email (como username) y contraseña."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is None:
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

        login(request, user)
        return _redirect_by_role(user)

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def cuenta_suspendida(request):
    return render(request, 'accounts/cuenta_suspendida.html')


def _redirect_by_role(user):
    """Redirige al usuario según su rol."""
    # Superadmin por rol de app O superusuario Django (creado con createsuperuser)
    if user.is_superadmin or user.is_superuser:
        return redirect('admin_panel:index')
    if user.is_gerente:
        return redirect('dashboard:index')
    # Vendedor
    return redirect('campo:index')
