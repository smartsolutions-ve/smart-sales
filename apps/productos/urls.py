from django.urls import path
from . import views

app_name = 'productos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('buscar/', views.buscar_json, name='buscar_json'),
    path('alertas/', views.alertas_stock, name='alertas_stock'),
    path('<int:pk>/stock-minimo/', views.configurar_stock_minimo, name='configurar_stock_minimo'),
]
