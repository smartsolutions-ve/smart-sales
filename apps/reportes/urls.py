from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('vendedores/', views.vendedores, name='vendedores'),
    path('clientes/', views.clientes, name='clientes'),
]
