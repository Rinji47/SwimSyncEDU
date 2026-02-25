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
    # path('edit_private_class_price/<int:class_id>/', views.edit_private_class_price, name='edit_private_class_price'),

    # Manage Private Class Prices
    path('manage_private_class_prices/', views.manage_private_class_prices, name='manage_private_class_prices'),
    path('new_private_class_price/', views.new_private_class_price, name='new_private_class_price'),
    
    # User booking URLs
    path('book_class/<int:class_id>/', views.book_class, name='book_class'),
    path('cancel_booked_class/<int:booking_id>/', views.cancel_booked_class, name='cancel_booked_class'),
    path('my_bookings/', views.my_bookings, name='my_bookings'),

    # User Private class booking flow
    path('select_trainer_for_private_class/<int:pool_id>/', views.select_trainer_for_private_class, name='select_trainer_for_private_class'),
    path('book_private_class/<int:pool_id>/<int:trainer_id>/', views.book_private_class, name='book_private_class'),
    path('my_private_classes/', views.my_private_classes, name='my_private_classes'),
    path('cancel_private_class/<int:private_class_id>/', views.cancel_private_class, name='cancel_private_class'),

    # Trainer attendance management helpers
    path('trainer/manage/group-classes/', views.manage_trainer_class_session, name='manage_trainer_class_session'),
    path('trainer/manage/private-classes/', views.manage_trainer_private_classes, name='manage_trainer_private_classes'),
    path('trainer/manage/group-class/<int:class_session_id>/attendance-history/', views.select_class_sessions_for_attendance_history, name='select_class_sessions_for_attendance_history'),
    path('trainer/manage/private-class/<int:private_class_id>/attendance-history/', views.select_private_classes_for_attendance_history, name='select_private_classes_for_attendance_history'),
    path('trainer/manage/substitute-group-classes/', views.trainer_susitute_class_sessions_list, name='trainer_susitute_class_sessions_list'),
    path('trainer/manage/substitute-private-classes/', views.trainer_susitute_private_classes_list, name='trainer_susitute_private_classes_list'),
]
