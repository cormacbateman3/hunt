from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
]
