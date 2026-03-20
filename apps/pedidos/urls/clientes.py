from django.urls import path
from apps.pedidos import views_clientes

app_name = 'clientes'

urlpatterns = [
    path('', views_clientes.lista, name='lista'),
    path('nuevo/', views_clientes.crear, name='crear'),
    path('<int:pk>/', views_clientes.detalle, name='detalle'),
    path('<int:pk>/editar/', views_clientes.editar, name='editar'),
    path('<int:pk>/eliminar/', views_clientes.eliminar, name='eliminar'),
]
