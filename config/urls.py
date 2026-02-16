"""
KeystoneBid URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # App URLs
    path('accounts/', include('apps.accounts.urls')),
    path('listings/', include('apps.listings.urls')),
    path('collections/', include('apps.collections.urls')),
    path('bids/', include('apps.bids.urls')),
    path('payments/', include('apps.payments.urls')),

    # Homepage
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "KeystoneBid Administration"
admin.site.site_title = "KeystoneBid Admin"
admin.site.index_title = "Welcome to KeystoneBid Administration"
