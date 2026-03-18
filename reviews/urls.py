from django.urls import path
from . import views

urlpatterns = [
    path('', views.select_trainer_from_certificate, name='select_trainer_from_certificate'),
    path('certificate/<int:certificate_id>/review/', views.review_trainer, name='review_trainer'),
    path('certificate/<int:certificate_id>/review/new/', views.create_review, name='create_review'),
    path('certificate/<int:certificate_id>/review/view/', views.view_review, name='view_review'),
    path('certificate/<int:certificate_id>/review/edit/', views.edit_review, name='edit_review'),
    path('certificate/<int:certificate_id>/review/delete/', views.delete_review, name='delete_review'),
    path('certificate/<int:certificate_id>/view/', views.view_certificate, name='view_certificate'),
    path('certificate/<int:certificate_id>/export/pdf/', views.export_certificate_pdf, name='export_certificate_pdf'),
]
