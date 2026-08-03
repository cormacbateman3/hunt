from django.urls import path

from . import views

app_name = 'offers'

urlpatterns = [
    path('listing/<int:listing_id>/make/', views.make_offer, name='make'),
    path('<int:offer_id>/', views.offer_detail, name='detail'),
    path('<int:offer_id>/counter/', views.counter_offer, name='counter'),
    path('<int:offer_id>/action/<str:action>/', views.offer_action, name='action'),
    path('mine/', views.my_offers, name='mine'),
]
