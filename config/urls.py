"""
Backtag URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView


from apps.accounts import views as account_views
from apps.collections import views as collection_views
from apps.core import views as core_views
from apps.listings import views as listing_views

urlpatterns = [
    # Admin — Django admin edits rows; /staff/ is the front door that
    # answers "what gets worse if I don't touch it today" (Pass 11).
    path('admin/', admin.site.urls),
    path('staff/', include(('apps.staff.urls', 'staff'), namespace='staff')),

    # The four zones. Each has a job: The Market is one catalog,
    # Collections is people and what they own, Research is what the
    # community knows, the Dashboard is your workspace. Top-level,
    # because they are the navigation. The URL *names* keep their old
    # words on purpose — hundreds of reverses and letters point at them;
    # only the paths people see changed with the Backtag rename.
    path('market/', listing_views.HuntView.as_view(), name='hunt'),
    path('market/map/', listing_views.hunt_map, name='hunt_map'),
    path('collections/', collection_views.collections_zone, name='collectors'),
    path('dashboard/', account_views.bench, name='bench'),
    path('research/', core_views.research, name='research'),
    path('research/field-guide/', core_views.almanac, name='almanac'),
    path('research/archives/', core_views.archives, name='archives'),

    # The old paths keep working forever — bookmarks, letters already
    # sent, and muscle memory all land where they meant to.
    path('hunt/', RedirectView.as_view(pattern_name='hunt', permanent=True,
                                       query_string=True)),
    path('hunt/map/', RedirectView.as_view(pattern_name='hunt_map',
                                           permanent=True, query_string=True)),
    path('bench/', RedirectView.as_view(pattern_name='bench', permanent=True,
                                        query_string=True)),
    path('almanac/', RedirectView.as_view(pattern_name='almanac',
                                          permanent=True, query_string=True)),

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
admin.site.site_header = "Backtag Administration"
admin.site.site_title = "Backtag Admin"
admin.site.index_title = "Welcome to Backtag Administration"
