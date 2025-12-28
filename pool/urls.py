from django.urls import path
from . import views

urlpatterns = [
    path('manage_pools/', views.manage_pools, name='manage_pools'),
]