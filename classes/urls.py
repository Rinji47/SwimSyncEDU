from django.urls import path
from . import views

urlpatterns = [
    # Manage Class Types
    path('manage_class_types/', views.manage_class_types, name='manage_class_types'),
    path('edit_class_types/<int:class_type_id>/', views.manage_class_types, name='edit_class_types'),
    path('close_class_type/<int:class_type_id>/', views.close_class_type, name='close_class_type'),

    # Manage Class Sessions
    path('manage_classes/', views.manage_class_sessions, name='manage_classes'),
    path('edit_classes/<int:class_id>/', views.manage_class_sessions, name='edit_class'),
    path('close_class_session/<int:class_id>/', views.close_class_session, name='close_class_session'),

    # Class Session Creation Flow
    path('select_pool_for_class_session/', views.select_pool_for_class_session, name='select_pool_for_class_session'),
    path('select_trainer_for_class_session/<int:pool_id>/', views.select_trainer_for_class_session, name='select_trainer_for_class_session'),
    path('create_class_session_for_pool/<int:pool_id>/<int:trainer_id>/', views.create_class_session_for_pool, name='create_class_session_for_pool'),

    # Manage Private Classes
    path('manage_private_classes/', views.manage_private_classes, name='manage_private_classes'),
    path('edit_private_class_price/<int:class_id>/', views.edit_private_class_price, name='edit_private_class_price'),

    # Manage Private Class Prices
    path('manage_private_class_prices/', views.manage_private_class_prices, name='manage_private_class_prices'),
    path('new_private_class_price/', views.new_private_class_price, name='new_private_class_price'),
]