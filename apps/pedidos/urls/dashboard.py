from django.urls import path
from apps.pedidos import views_dashboard

app_name = 'dashboard'

urlpatterns = [
    path('', views_dashboard.index, name='index'),
]
