from django.urls import path
from . import views

app_name = 'collections'

urlpatterns = [
    path('my/', views.my_collection, name='my_collection'),
    path('create/', views.collection_item_create, name='create'),
    path('<int:pk>/edit/', views.collection_item_edit, name='edit'),
    path('<int:pk>/delete/', views.collection_item_delete, name='delete'),
    path('wanted/create/', views.wanted_item_create, name='wanted_create'),
    path('wanted/<int:pk>/edit/', views.wanted_item_edit, name='wanted_edit'),
    path('wanted/<int:pk>/delete/', views.wanted_item_delete, name='wanted_delete'),
    path('add-from-order/<int:order_id>/', views.add_from_order, name='add_from_order'),
]
