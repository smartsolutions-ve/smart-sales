"""URLs del módulo de Devoluciones y Notas de Crédito."""
from django.urls import path

from . import views

app_name = 'devoluciones'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/aprobar/', views.aprobar, name='aprobar'),
    path('<int:pk>/completar/', views.completar, name='completar'),
    path('<int:pk>/rechazar/', views.rechazar, name='rechazar'),
    path('pedido/<int:pedido_pk>/items/', views.pedido_items_json, name='pedido_items'),
    path('pedidos-por-cliente/', views.pedidos_por_cliente_json, name='pedidos_por_cliente'),
]
