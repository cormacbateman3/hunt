from django.urls import path
from . import views

app_name = 'trades'

urlpatterns = [
    path('listing/<int:listing_id>/propose/', views.propose_offer, name='propose'),
    path('offers/<int:offer_id>/', views.offer_detail, name='offer_detail'),
    path('offers/<int:offer_id>/counter/', views.counter_offer, name='counter_offer'),
    path('offers/<int:offer_id>/action/<str:action>/', views.offer_action, name='offer_action'),
    path('<int:trade_id>/', views.trade_detail, name='trade_detail'),
]
