"""URLs del panel de superadmin de SmartSales."""
from django.urls import path
from . import views_admin

app_name = 'admin_panel'

urlpatterns = [
    path('', views_admin.index, name='index'),
    path('orgs/', views_admin.org_lista, name='org_lista'),
    path('orgs/nueva/', views_admin.org_crear, name='org_crear'),
    path('orgs/<int:pk>/', views_admin.org_detalle, name='org_detalle'),
    path('orgs/<int:pk>/editar/', views_admin.org_editar, name='org_editar'),
    path('orgs/<int:pk>/toggle/', views_admin.org_toggle_activa, name='org_toggle'),
    path('orgs/<int:pk>/usuarios/', views_admin.org_usuarios, name='org_usuarios'),
    path('orgs/<int:pk>/usuarios/nuevo/', views_admin.usuario_crear, name='usuario_crear'),
    path('orgs/<int:org_pk>/usuarios/<int:user_pk>/editar/', views_admin.usuario_editar, name='usuario_editar'),
    path('orgs/<int:org_pk>/usuarios/<int:user_pk>/eliminar/', views_admin.usuario_eliminar, name='usuario_eliminar'),
    path('orgs/<int:org_pk>/usuarios/<int:user_pk>/password/', views_admin.usuario_cambiar_password, name='usuario_password'),
]
