from django.urls import path
from apps.pedidos import views_pedidos

app_name = 'pedidos'

urlpatterns = [
    path('', views_pedidos.lista, name='lista'),
    path('nuevo/', views_pedidos.crear, name='crear'),
    path('<int:pk>/', views_pedidos.detalle, name='detalle'),
    path('<int:pk>/editar/', views_pedidos.editar, name='editar'),
    path('<int:pk>/eliminar/', views_pedidos.eliminar, name='eliminar'),
    path('<int:pk>/estado/', views_pedidos.cambiar_estado, name='cambiar_estado'),
    path('<int:pk>/estado-despacho/', views_pedidos.cambiar_estado_despacho, name='cambiar_estado_despacho'),
]
