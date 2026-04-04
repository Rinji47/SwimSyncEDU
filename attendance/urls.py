from django.urls import path
from . import views

urlpatterns = [
    path('admin/select_trainer/', views.select_trainer_for_attendance, name='select_trainer_for_attendance'),
    path('admin/trainer-history/', views.select_trainer_for_attendance_history, name='select_trainer_for_attendance_history'),
    path('admin/trainer-history/<int:trainer_id>/', views.trainers_attandance_history, name='trainers_attandance_history'),
    path('admin/trainer/<int:trainer_id>/mark/', views.mark_trainer_attendance, name='mark_trainer_attendance'),
    path('admin/absent/group-classes/', views.list_ongoing_classes_of_absent_trainer, name='list_ongoing_classes_of_absent_trainer'),
    path('admin/absent/private-classes/', views.list_ongoing_private_classes_of_absent_trainer, name='list_ongoing_private_classes_of_absent_trainer'),
    path('admin/group-class/<int:class_session_id>/assign-substitute/', views.assign_substitute_trainer_for_class_session, name='assign_substitute_trainer_for_class_session'),
    path('admin/group-class/<int:class_session_id>/choose-substitute/', views.choose_substitute_trainer_for_class_session, name='choose_substitute_trainer_for_class_session'),
    path('admin/group-class/<int:class_session_id>/cancel-today/', views.cancel_group_class_for_today, name='cancel_group_class_for_today'),
    path('admin/private-class/<int:private_class_id>/assign-substitute/', views.assign_substitute_trainer_for_private_class, name='assign_substitute_trainer_for_private_class'),
    path('admin/private-class/<int:private_class_id>/choose-substitute/', views.choose_substitute_trainer_for_private_class, name='choose_substitute_trainer_for_private_class'),
    path('admin/private-class/<int:private_class_id>/cancel-today/', views.cancel_private_class_for_today, name='cancel_private_class_for_today'),
    path('admin/trainer/<int:trainer_id>/classes/', views.list_trainer_classes, name='list_trainer_classes'),

    path('admin/list-of-group-classes-for-attendance-history/', views.admin_class_session_list_for_attendance_history, name='admin_list_to_check_class_session_attendance_history'),
    path('admin/list-of-private-classes-for-attendance-history/', views.admin_private_class_list_for_attendance_history, name='admin_list_to_check_private_class_attendance_history'),
    path('admin/group-class/<int:class_session_id>/history/', views.class_session_attendance_history, name='admin_class_session_attendance_history'),
    path('admin/private-class/<int:private_class_id>/history/', views.private_class_attendance_history, name='admin_private_class_attendance_history'),
    path('admin/class-private-history/', views.class_and_private_classes_cancellation_and_substitute_history, name='class_private_activity_history'),
    path('admin/group-class/<int:class_session_id>/activity-detail/', views.admin_group_class_activity_detail, name='admin_group_class_activity_detail'),
    path('admin/private-class/<int:private_class_id>/activity-detail/', views.admin_private_class_activity_detail, name='admin_private_class_activity_detail'),

    path('trainer/group-classes/', views.select_class_for_attendance, name='select_class_for_attendance'),
    path('trainer/group-class/<int:class_session_id>/students/', views.select_student_for_attendance, name='select_student_for_attendance'),
    path('trainer/group-class-booking/<int:class_booking_id>/mark/', views.mark_class_attendance, name='mark_class_attendance'),
    path('trainer/private-classes/', views.select_private_class_for_attendance, name='select_private_class_for_attendance'),
    path('trainer/private-class/<int:private_class_id>/mark/', views.mark_private_class_attendance, name='mark_private_class_attendance'),
    path('trainer/group-class/<int:class_session_id>/history/', views.class_session_attendance_history, name='class_session_attendance_history'),
    path('trainer/private-class/<int:private_class_id>/history/', views.private_class_attendance_history, name='private_class_attendance_history'),
]
