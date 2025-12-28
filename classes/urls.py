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
]