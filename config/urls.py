"""
KeystoneBid URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


from apps.accounts import views as account_views
from apps.collections import views as collection_views
from apps.core import views as core_views
from apps.listings import views as listing_views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # The four zones. Each has a job: Hunt is one catalog, Collections is
    # people and what they own, My Bench is your workspace, The Almanac is
    # what the community knows. Top-level, because they are the navigation.
    path('hunt/', listing_views.HuntView.as_view(), name='hunt'),
    path('collections/', collection_views.browse_collections, name='collectors'),
    path('bench/', account_views.bench, name='bench'),
    path('almanac/', core_views.almanac, name='almanac'),

    # App URLs
    path('accounts/', include('apps.accounts.urls')),
    path('', include(('apps.core.urls', 'core'), namespace='core')),
    path('listings/', include(('apps.listings.urls', 'listings'), namespace='listings')),
    path('collections/', include('apps.collections.urls')),
    path('bids/', include('apps.bids.urls')),
    path('orders/', include('apps.orders.urls')),
    path('payments/', include('apps.payments.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('shipping/', include('apps.shipping.urls')),
    path('trades/', include('apps.trades.urls')),
    path('offers/', include('apps.offers.urls')),
    path('favorites/', include('apps.favorites.urls')),
    path('messages/', include(('apps.messaging.urls', 'messaging'), namespace='messaging')),
    path('reviews/', include(('apps.reviews.urls', 'reviews'), namespace='reviews')),
    path('', include(('apps.prefill.urls', 'prefill'), namespace='prefill')),

    # Homepage
    path('', core_views.home, name='home'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "KeystoneBid Administration"
admin.site.site_title = "KeystoneBid Admin"
admin.site.index_title = "Welcome to KeystoneBid Administration"
