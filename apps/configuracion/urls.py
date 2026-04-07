from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    # Vista principal con tabs Alpine.js
    path('', views.ConfiguracionView.as_view(), name='index'),

    # Logo
    path('logo/', views.logo_upload, name='logo_upload'),

    # Unidades de medida
    path('unidades/crear/', views.unidades_crear, name='unidades_crear'),
    path('unidades/<uuid:pk>/editar/', views.unidades_editar, name='unidades_editar'),
    path('unidades/<uuid:pk>/eliminar/', views.unidades_eliminar, name='unidades_eliminar'),

    # Listas de precios
    path('listas/crear/', views.listas_crear, name='listas_crear'),
    path('listas/<uuid:pk>/editar/', views.listas_editar, name='listas_editar'),
    path('listas/<uuid:pk>/eliminar/', views.listas_eliminar, name='listas_eliminar'),

    # Métodos de pago
    path('metodos/crear/', views.metodos_crear, name='metodos_crear'),
    path('metodos/<uuid:pk>/editar/', views.metodos_editar, name='metodos_editar'),
    path('metodos/<uuid:pk>/eliminar/', views.metodos_eliminar, name='metodos_eliminar'),

    # Zonas de despacho
    path('zonas/crear/', views.zonas_crear, name='zonas_crear'),
    path('zonas/<uuid:pk>/editar/', views.zonas_editar, name='zonas_editar'),
    path('zonas/<uuid:pk>/eliminar/', views.zonas_eliminar, name='zonas_eliminar'),

    # Tasa de cambio
    path('moneda/', views.tasa_cambio_actualizar, name='tasa_cambio'),
]
