"""
URLs del módulo de Cuentas por Cobrar (CxC).
"""
from django.urls import path

from . import views

app_name = 'cxc'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('cliente/<int:pk>/', views.cliente_detalle, name='cliente_detalle'),
    path('cliente/<int:pk>/pagar/', views.registrar_pago, name='registrar_pago'),
    path('aging/', views.aging_report, name='aging'),
    path('aging/csv/', views.aging_csv, name='aging_csv'),
]
