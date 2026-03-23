from django.urls import path
from . import views

app_name = 'chat_ia'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('ask/', views.ask_view, name='ask'),
]
