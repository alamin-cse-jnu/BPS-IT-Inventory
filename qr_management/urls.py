from django.urls import path
from . import views

app_name = 'qr_management'
urlpatterns = [
    path('', views.qr_index, name='index'),
]