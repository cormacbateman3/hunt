from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:order_id>/', views.create_checkout_session, name='checkout'),
    path('success/<int:order_id>/', views.payment_success, name='success'),
    path('cancel/<int:order_id>/', views.payment_cancel, name='cancel'),
    path('checkout/transaction/<int:transaction_id>/', views.legacy_checkout_redirect, name='legacy_checkout'),
    path('webhook/', views.stripe_webhook, name='webhook'),
]
