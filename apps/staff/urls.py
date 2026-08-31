from django.urls import path

from apps.staff import views

app_name = 'staff'

urlpatterns = [
    path('', views.desk, name='desk'),
    path('moderation/', views.moderation_queue, name='moderation'),
    path('moderation/message/<int:message_id>/', views.scan_view, name='scan'),
    path('moderation/event/<int:pk>/act/', views.event_action, name='event_action'),
    path('moderation/message/<int:pk>/act/', views.message_action, name='message_action'),
]
