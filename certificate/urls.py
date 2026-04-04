from django.urls import path
from . import views

urlpatterns = [
    path('trainer/certificates/group/', views.pending_group_certificate_sessions, name='pending_group_certificate_sessions'),
    path('trainer/certificates/group/<int:class_session_id>/', views.select_student_for_group_certificate, name='select_student_for_group_certificate'),
    path('trainer/certificates/group/issue/<int:booking_id>/', views.issue_group_class_completion_certificate, name='issue_group_class_completion_certificate'),
    path('trainer/certificates/private/', views.pending_private_certificates, name='pending_private_certificates'),
    path('trainer/certificates/private/issue/<int:private_class_id>/', views.issue_private_class_completion_certificate, name='issue_private_class_completion_certificate'),
    path('granted/', views.certificate_granted_list, name='certificate_granted_list'),
    path('admin/view/<int:certificate_id>/', views.admin_view_certificate, name='admin_view_certificate'),
]
