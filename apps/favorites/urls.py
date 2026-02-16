from django.urls import path
from . import views

app_name = 'favorites'

urlpatterns = [
    path('', views.favorites_list, name='list'),
    path('listings/<int:pk>/toggle/', views.toggle_listing_favorite, name='toggle_listing'),
    path('collection-items/<int:pk>/toggle/', views.toggle_collection_item_favorite, name='toggle_collection_item'),
]
