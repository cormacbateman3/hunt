from django.urls import path
from . import views

app_name = 'bids'

urlpatterns = [
    path('<int:listing_id>/place/', views.bid_create, name='create'),
    path('<int:listing_id>/status/', views.bid_status, name='status'),
    path('my-bids/', views.my_bids, name='my_bids'),
]
