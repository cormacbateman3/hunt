from django.urls import path

from apps.core import views

app_name = 'core'

urlpatterns = [
    path('api/geo-units/', views.geo_units_api, name='geo_units_api'),
    path('api/map/', views.map_data_api, name='map_data_api'),
    path('api/license-types/', views.license_types_api, name='license_types_api'),
    path('reference-suggestions/new/', views.create_reference_data_suggestion, name='suggestion_create'),
    path('states/<slug:slug>/', views.state_detail, name='state_detail'),
    path('geographic-units/<int:pk>/', views.geographic_unit_detail, name='geographic_unit_detail'),
]
