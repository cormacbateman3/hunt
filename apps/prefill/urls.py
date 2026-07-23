from django.urls import path

from apps.prefill import views

app_name = 'prefill'

urlpatterns = [
    path('api/prefill/jobs/', views.create_job, name='create_job'),
    path('api/prefill/jobs/<int:pk>/', views.job_status, name='job_status'),
    path('api/prefill/jobs/<int:pk>/corrections/', views.job_corrections, name='job_corrections'),
]
