from django.urls import path
from . import views

app_name = 'collections'

urlpatterns = [
    path('my/', views.my_collection, name='my_collection'),
    path('create/', views.collection_item_create, name='create'),
    path('<int:pk>/edit/', views.collection_item_edit, name='edit'),
]
