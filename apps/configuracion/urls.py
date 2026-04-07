from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    path('', views.ConfiguracionView.as_view(), name='index'),
    # Futuras URLs HTMX para CRUD de catálogos irán aquí
]
