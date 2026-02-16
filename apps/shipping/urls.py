from django.urls import path
from . import views

app_name = 'shipping'

urlpatterns = [
    path('orders/<int:pk>/quote/', views.quote_order_shipping_view, name='quote_order_shipping'),
    path('orders/<int:pk>/buy-label/', views.buy_label_view, name='buy_label'),
    path('orders/<int:pk>/manual-tracking/', views.manual_tracking_view, name='manual_tracking'),
    path('webhooks/shippo/', views.shippo_webhook, name='shippo_webhook'),
]
