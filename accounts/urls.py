from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('trainer_dashboard/', views.trainer_dashboard, name='trainer_dashboard'),
    path('user_dashboard/', views.user_dashboard, name='user_dashboard'),
    path('profile/', views.user_profile, name='user_profile'),
    path('trainer/profile/', views.trainer_profile, name='trainer_profile'),
    path('admin/profile/', views.admin_profile, name='admin_profile'),
    path('change_password/', views.change_password, name='change_password'),

    path('members/', views.manage_members, name='manage_members'),
    path('members/add/', views.add_member, name='add_member'),
    path('members/view/<int:member_id>/', views.view_member, name='view_member'),
    path('members/edit/<int:member_id>/', views.edit_member, name='edit_member'),
    path('members/toggle_status/<int:member_id>/', views.toggle_member_status, name='toggle_member_status'),

    path('trainers/', views.manage_trainer, name='manage_trainers'),
    path('trainers/add/', views.add_trainer, name='add_trainer'),
    path('trainers/view/<int:trainer_id>/', views.view_trainer, name='view_trainer'),
    path('trainers/edit/<int:trainer_id>/', views.edit_trainer, name='edit_trainer'),
    path('trainers/toggle_status/<int:trainer_id>/', views.toggle_trainer_status, name='toggle_trainer_status'),

    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/done/', views.password_reset_done_view, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete_view, name='password_reset_complete'),
    path('private-classes/<int:private_class_id>/cancel/', views.admin_cancel_private_class, name='admin_cancel_private_class'),
    path('private-classes/<int:private_class_id>/open/', views.admin_open_private_class, name='admin_open_private_class'),
]
