from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:transaction_id>/', views.create_checkout_session, name='checkout'),
    path('success/<int:transaction_id>/', views.payment_success, name='success'),
    path('cancel/<int:transaction_id>/', views.payment_cancel, name='cancel'),
    path('webhook/', views.stripe_webhook, name='webhook'),
]
