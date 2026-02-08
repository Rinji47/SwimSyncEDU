from django.urls import path
from . import views

urlpatterns = [
    path('nearby/', views.nearby_pools, name='nearby_pools'),
    path('manage_pools/', views.manage_pools, name='manage_pools'),
    path('edit_pool/<int:pool_id>/', views.manage_pools, name='edit_pool'),
    path('close_pool/<int:pool_id>/', views.close_pool, name='close_pool'),

    path('qualities/', views.manage_quality, name='manage_quality'),
    path('qualities/add/', views.add_quality, name='add_quality'),
    path('qualities/edit/<int:quality_id>/', views.edit_quality, name='edit_quality'),
    path('qualities/delete/<int:quality_id>/', views.delete_quality, name='delete_quality'),
]