from django.urls import path
from . import views

app_name = 'flotas'

urlpatterns = [
    # Viajes
    path('', views.viajes_lista, name='lista'),
    path('nuevo/', views.viaje_crear, name='crear'),
    path('dashboard/', views.dashboard_flotas, name='dashboard'),
    path('<int:pk>/', views.viaje_detalle, name='detalle'),
    path('<int:pk>/editar/', views.viaje_editar, name='editar'),
    path('<int:pk>/estado/', views.viaje_cambiar_estado, name='cambiar_estado'),
    path('<int:pk>/eliminar/', views.viaje_eliminar, name='eliminar'),
    # Vehículos
    path('vehiculos/', views.vehiculos_lista, name='vehiculos'),
    path('vehiculos/nuevo/', views.vehiculo_crear, name='vehiculo_crear'),
    path('vehiculos/<int:pk>/editar/', views.vehiculo_editar, name='vehiculo_editar'),
]
