from django.urls import path
from . import views

app_name = 'despacho'

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:pk>/estado/', views.cambiar_estado_despacho, name='cambiar_estado'),
]
