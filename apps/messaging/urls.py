from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start/', views.start_conversation_view, name='start'),
    path('group/new/', views.group_new, name='group_new'),
    path('people/', views.user_search, name='user_search'),
    path('<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('<int:pk>/members/add/', views.group_add_member, name='group_add_member'),
    path('<int:pk>/leave/', views.group_leave, name='group_leave'),
    path('<int:pk>/members/<int:user_id>/remove/', views.group_remove_member, name='group_remove_member'),
    path('<int:pk>/block/', views.block_user_view, name='block_user'),
    path('<int:pk>/report/', views.report_conversation_view, name='report_conversation'),
    path('<int:pk>/messages/<int:message_id>/report/', views.report_message_view, name='report_message'),
    path('unblock/<int:user_id>/', views.unblock_user_view, name='unblock_user'),
    # Blocking used to require a conversation, so the only way to block
    # somebody was to be mid-argument with them. This one takes a person.
    path('block-person/<int:user_id>/', views.block_person_view, name='block_person'),
]
