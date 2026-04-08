"""URLs del módulo de Visitas Comerciales."""

from django.urls import path

from . import views

app_name = 'visitas'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/realizada/', views.marcar_realizada, name='marcar_realizada'),
]
