from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.center, name='center'),
    path('<int:pk>/go/', views.go, name='go'),
    path('<int:pk>/mark-read/', views.mark_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
]

