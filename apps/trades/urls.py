from django.urls import path
from . import views

app_name = 'trades'

urlpatterns = [
    path('listing/<int:listing_id>/propose/', views.propose_offer, name='propose'),
    path('offers/<int:offer_id>/', views.offer_detail, name='offer_detail'),
    path('offers/<int:offer_id>/counter/', views.counter_offer, name='counter_offer'),
    path('offers/<int:offer_id>/action/<str:action>/', views.offer_action, name='offer_action'),
    path('<int:trade_id>/shipments/<int:shipment_id>/manual-tracking/', views.trade_shipment_manual_tracking, name='trade_shipment_manual_tracking'),
    path('<int:trade_id>/shipments/<int:shipment_id>/buy-label/', views.trade_shipment_buy_label, name='trade_shipment_buy_label'),
    path('<int:trade_id>/shipments/<int:shipment_id>/confirm-receipt/', views.trade_confirm_receipt, name='trade_confirm_receipt'),
    path('<int:trade_id>/', views.trade_detail, name='trade_detail'),
]
