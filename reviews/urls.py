from django.urls import path
from . import views
from certificate.views import user_view_certificate

urlpatterns = [
    path('', views.user_select_trainer_from_certificate, name='user_select_trainer_from_certificate'),
    path('trainers/', views.public_select_trainer_for_reviews, name='public_select_trainer_for_reviews'),
    path('trainers/<int:trainer_id>/reviews/', views.public_trainer_review_list, name='public_trainer_review_list'),
    path('trainer/my-reviews/', views.trainer_my_reviews, name='trainer_my_reviews'),
    path('trainer/reviews/<int:review_id>/view/', views.trainer_view_review_detail, name='trainer_view_review_detail'),
    path('admin/all-reviews/', views.admin_all_trainer_reviews, name='admin_all_trainer_reviews'),
    path('admin/reviews/<int:review_id>/view/', views.admin_view_review_detail, name='admin_view_review_detail'),
    path('admin/reviews/<int:review_id>/inactive/', views.admin_inactive_reviews, name='admin_inactive_reviews'),
    path('admin/reviews/<int:review_id>/active/', views.admin_active_reviews, name='admin_active_reviews'),
    path('certificate/<int:certificate_id>/review/', views.user_review_trainer, name='user_review_trainer'),
    path('certificate/<int:certificate_id>/review/new/', views.user_create_review, name='user_create_review'),
    path('certificate/<int:certificate_id>/review/view/', views.user_view_review, name='user_view_review'),
    path('certificate/<int:certificate_id>/review/edit/', views.user_edit_review, name='user_edit_review'),
    path('certificate/<int:certificate_id>/review/delete/', views.user_delete_review, name='user_delete_review'),
    path('certificate/<int:certificate_id>/view/', user_view_certificate, name='user_view_certificate'),
]
