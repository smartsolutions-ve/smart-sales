from django.urls import path
from . import views

app_name = 'productos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('buscar/', views.buscar_json, name='buscar_json'),
]
