from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """
    Decorador que restringe el acceso a usuarios con los roles especificados.

    Uso:
        @role_required('gerente')
        @role_required('gerente', 'superadmin')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role not in roles:
                messages.error(request, 'No tienes permiso para acceder a esta sección.')
                return redirect('accounts:login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def superadmin_required(view_func):
    """Decorador que restringe el acceso exclusivamente al superadmin (rol app o Django is_superuser)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_superadmin and not request.user.is_superuser:
            messages.error(request, 'Acceso restringido al administrador de SmartSales.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def dashboard_required(view_func):
    """Restringe acceso al dashboard gerencial (gerente o superadmin)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.can_access_dashboard:
            # Vendedores van al campo
            return redirect('campo:index')
        return view_func(request, *args, **kwargs)
    return wrapper
