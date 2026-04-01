from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('order/<int:order_id>/', views.submit_order_review, name='submit_order'),
    path('trade/<int:trade_id>/', views.submit_trade_review, name='submit_trade'),
]
