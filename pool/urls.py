from django.urls import path
from . import views

urlpatterns = [
    path('nearby/', views.nearby_pools, name='nearby_pools'),
    path('pool/<int:pool_id>/classes/', views.pool_class_types, name='pool_class_types'),
    path('pool/<int:pool_id>/classes/<int:class_type_id>/', views.pool_classes, name='pool_classes'),
    path('manage_pools/', views.manage_pools, name='manage_pools'),
    path('edit_pool/<int:pool_id>/', views.manage_pools, name='edit_pool'),
    path('close_pool/<int:pool_id>/', views.close_pool, name='close_pool'),

    path('qualities/', views.manage_quality, name='manage_quality'),
    path('qualities/add/', views.add_quality, name='add_quality'),
    path('qualities/edit/<int:quality_id>/', views.edit_quality, name='edit_quality'),
    path('qualities/delete/<int:quality_id>/', views.delete_quality, name='delete_quality'),

    # Trainer assignment workflow
    path('admin/assign_trainer_manager/', views.assign_trainer_manager, name='assign_trainer_manager'),
    path('admin/list_pools/', views.list_pools, name='list_pools'),
    path('admin/list_trainers/<int:pool_id>/', views.list_trainers, name='list_trainers'),
    path('admin/assign_trainer/<int:pool_id>/<int:trainer_id>/', views.assign_trainer, name='assign_trainer'),
    path('admin/unassign_trainer/<int:assignment_id>/', views.unassign_trainer, name='unassign_trainer'),
]