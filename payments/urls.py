from django.urls import path
from . import views

urlpatterns = [
    path('report/', views.payment_report, name='payment_report'),
    path('admin-report/', views.admin_payment_report, name='admin_payment_report'),
    path('khalti/start/<str:uid>/', views.khalti_payment_start, name='khalti_payment_start'),
    path('khalti/verify/<str:uid>/', views.khalti_payment_verify, name='khalti_payment_verify'),
    path('group-class/<int:class_id>/checkout/', views.group_class_payment_checkout, name='group_class_payment_checkout'),
    path('group-class/<int:class_id>/cancel/', views.group_class_payment_cancel, name='group_class_payment_cancel'),
    path('group-class/success/<str:uid>/', views.group_class_payment_success, name='group_class_payment_success'),
    path('group-class/failure/<str:uid>/', views.group_class_payment_failure, name='group_class_payment_failure'),
    path('private-class/checkout/', views.private_class_payment_checkout, name='private_class_payment_checkout'),
    path('private-class/cancel/', views.private_class_payment_cancel, name='private_class_payment_cancel'),
    path('private-class/success/<str:uid>/', views.private_class_payment_success, name='private_class_payment_success'),
    path('private-class/failure/<str:uid>/', views.private_class_payment_failure, name='private_class_payment_failure'),
]
