from django.urls import path
from . import views

app_name = 'cuotas'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('por-zona/', views.resumen_zona, name='resumen_zona'),
    path('por-vendedor/', views.resumen_vendedor, name='resumen_vendedor'),
    path('por-producto/', views.resumen_producto, name='resumen_producto'),
    path('importar/', views.importar, name='importar'),
    path('exportar-csv/', views.exportar_csv, name='exportar_csv'),
    path('tasas/', views.tasas_lista, name='tasas'),
    path('tasas/nueva/', views.tasa_crear, name='tasa_crear'),
    path('tasas/<int:pk>/editar/', views.tasa_editar, name='tasa_editar'),
    path('tasas/<int:pk>/eliminar/', views.tasa_eliminar, name='tasa_eliminar'),
]
