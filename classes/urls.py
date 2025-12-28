from django.urls import path
from . import views

urlpatterns = [
    path('manage_classes/', views.manage_class_sessions, name='manage_classes'),
    path('edit_classes/<int:class_id>/', views.manage_class_sessions, name='edit_class'),
    path('manage_class_types/', views.manage_class_types, name='manage_class_types'),
    path('cancel_class/<int:class_id>/', views.cancel_class_session, name='cancel_class'),
]