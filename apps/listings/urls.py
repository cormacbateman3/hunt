from django.urls import path
from . import views
from apps.bids import views as bid_views

app_name = 'listings'

urlpatterns = [
    path('', views.ListingListView.as_view(), name='list'),
    path('create/', views.listing_create, name='create'),
    path('<int:listing_id>/bid-status/', bid_views.bid_status, name='bid_status'),
    path('<int:pk>/', views.listing_detail, name='detail'),
    path('<int:pk>/edit/', views.listing_edit, name='edit'),
    path('my-listings/', views.my_listings, name='my_listings'),
]
