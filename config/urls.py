from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Raíz → redirige al login
    path('', RedirectView.as_view(url='/login/'), name='root'),

    # Django admin (solo para superadmin técnico — debug/emergencia)
    path('django-admin/', admin.site.urls),

    # Auth
    path('', include('apps.accounts.urls', namespace='accounts')),

    # Dashboard gerencial
    path('dashboard/', include('apps.pedidos.urls.dashboard', namespace='dashboard')),

    # Módulos
    path('pedidos/', include('apps.pedidos.urls.pedidos', namespace='pedidos')),
    path('clientes/', include('apps.pedidos.urls.clientes', namespace='clientes')),
    path('despacho/', include('apps.despacho.urls', namespace='despacho')),
    path('competencia/', include('apps.competencia.urls', namespace='competencia')),
    path('reportes/', include('apps.reportes.urls', namespace='reportes')),

    # Formulario móvil de campo
    path('campo/', include('apps.campo.urls', namespace='campo')),

    # Panel superadmin de SmartSales
    path('admin-panel/', include('apps.accounts.urls_admin', namespace='admin_panel')),
]

# Servir media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
