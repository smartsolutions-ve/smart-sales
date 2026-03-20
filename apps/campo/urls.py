from django.urls import path
from . import views

app_name = 'campo'

urlpatterns = [
    path('', views.index, name='index'),
    path('pedido/nuevo/', views.pedido_nuevo, name='pedido_nuevo'),
    path('competencia/nuevo/', views.competencia_nueva, name='competencia_nueva'),
]
