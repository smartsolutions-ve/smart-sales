from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('vendedores/', views.vendedores, name='vendedores'),
    path('vendedores/csv/', views.vendedores_csv, name='vendedores_csv'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/csv/', views.clientes_csv, name='clientes_csv'),
]
