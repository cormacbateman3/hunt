from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.my_orders, name='my_orders'),
    path('<int:pk>/', views.order_detail, name='detail'),
    path('<int:pk>/confirm-receipt/', views.confirm_receipt, name='confirm_receipt'),
    path('<int:pk>/update-status/', views.update_status, name='update_status'),
    path('<int:pk>/strikes/<int:strike_id>/initiate-excuse/', views.initiate_excuse, name='initiate_excuse'),
    path('<int:pk>/strikes/<int:strike_id>/confirm-excuse/', views.confirm_excuse, name='confirm_excuse'),
]
