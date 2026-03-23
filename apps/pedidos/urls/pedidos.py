from django.urls import path
from apps.pedidos import views_pedidos, views_facturas

app_name = 'pedidos'

urlpatterns = [
    path('', views_pedidos.lista, name='lista'),
    path('exportar-csv/', views_pedidos.exportar_csv, name='exportar_csv'),
    path('nuevo/', views_pedidos.crear, name='crear'),
    path('<int:pk>/', views_pedidos.detalle, name='detalle'),
    path('<int:pk>/pdf/', views_pedidos.detalle_pdf, name='detalle_pdf'),
    path('<int:pk>/editar/', views_pedidos.editar, name='editar'),
    path('<int:pk>/clonar/', views_pedidos.clonar, name='clonar'),
    path('<int:pk>/eliminar/', views_pedidos.eliminar, name='eliminar'),
    path('<int:pk>/estado/', views_pedidos.cambiar_estado, name='cambiar_estado'),
    path('<int:pk>/estado-despacho/', views_pedidos.cambiar_estado_despacho, name='cambiar_estado_despacho'),
    # Facturas
    path('<int:pedido_pk>/facturas/nueva/', views_facturas.agregar_factura, name='factura_crear'),
    path('facturas/<int:pk>/eliminar/', views_facturas.eliminar_factura, name='factura_eliminar'),
]
