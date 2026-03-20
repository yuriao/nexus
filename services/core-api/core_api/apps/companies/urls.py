from django.urls import path

from .views import (
    AlertListCreateView,
    CompanyDataPointListView,
    CompanyDetailView,
    CompanyListCreateView,
    WatchListView,
)

urlpatterns = [
    path("", CompanyListCreateView.as_view(), name="company-list"),
    path("<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
    path("<int:pk>/data-points/", CompanyDataPointListView.as_view(), name="company-datapoints"),
    path("<int:pk>/watchlist/", WatchListView.as_view(), name="company-watchlist"),
    path("alerts/", AlertListCreateView.as_view(), name="alert-list"),
]
