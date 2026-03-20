from django.urls import path
from . import views

app_name = 'competencia'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
