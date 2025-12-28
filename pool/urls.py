from django.urls import path
from . import views

urlpatterns = [
    path('manage_pools/', views.manage_pools, name='manage_pools'),
    path('edit_pool/<int:pool_id>/', views.manage_pools, name='edit_pool'),
    path('close_pool/<int:pool_id>/', views.close_pool, name='close_pool'),
]