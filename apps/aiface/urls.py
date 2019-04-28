from django.urls import path
from apps.aiface import views

urlpatterns = [
    path('', views.index),
    path('imageai', views.imageai),
]
