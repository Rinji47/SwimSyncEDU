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

    path('trainers/', views.manage_trainer, name='manage_trainers'),
    path('trainers/add/', views.add_trainer, name='add_trainer'),
    path('trainers/edit/<int:trainer_id>/', views.edit_trainer, name='edit_trainer'),
    path('trainers/toggle_status/<int:trainer_id>/', views.toggle_trainer_status, name='toggle_trainer_status'),
]