"""URLs del módulo de cotizaciones."""
from django.urls import path

from . import views

app_name = 'cotizaciones'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/pdf/', views.detalle_pdf, name='pdf'),
    path('<int:pk>/estado/', views.cambiar_estado, name='cambiar_estado'),
    path('<int:pk>/convertir/', views.convertir_a_pedido, name='convertir'),
]
