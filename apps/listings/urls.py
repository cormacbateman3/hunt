from django.urls import path
from . import views
from apps.bids import views as bid_views

app_name = 'listings'

urlpatterns = [
    path('', views.ListingListView.as_view(), name='list'),

    # The four pillars collapse into Hunt. Format became a filter, so each
    # old destination is now a position in the one catalog.
    path('auction-house/', views.pillar_redirect('auction'), name='auction_house'),
    path('general-store/', views.pillar_redirect('buy_now'), name='general_store'),
    path('trading-block/', views.pillar_redirect('trade'), name='trading_block'),
    # Step 1 is the front door. `create/` stays as step 2 so every existing
    # link into it keeps working.
    path('sell/', views.sell_start, name='sell_start'),
    path('create/', views.listing_create, name='create'),
    path('<int:listing_id>/bid-status/', bid_views.bid_status, name='bid_status'),
    path('<int:pk>/questions/ask/', views.ask_question, name='ask_question'),
    path('<int:pk>/questions/<int:question_id>/answer/', views.answer_question, name='answer_question'),
    path('<int:pk>/questions/<int:question_id>/flag/', views.flag_question, name='flag_question'),
    path('<int:pk>/buy-now/review/', views.buy_now_review, name='buy_now_review'),
    path('<int:pk>/buy-now/', views.buy_now_checkout_start, name='buy_now_checkout_start'),
    path('<int:pk>/won/review/', views.auction_win_review, name='auction_win_review'),
    path('<int:pk>/', views.listing_detail, name='detail'),
    path('<int:pk>/edit/', views.listing_edit, name='edit'),
    path('my-listings/', views.my_listings, name='my_listings'),
]
