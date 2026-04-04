from django.urls import path

from .views import (
    AlertListCreateView,
    CompanyDataPointListView,
    CompanyDetailView,
    CompanyListCreateView,
    WatchListView,
)
from .metrics_views import (
    CompanyMetricLatestView,
    CompanyMetricHistoryView,
    CompanyMetricExportView,
)

urlpatterns = [
    path("", CompanyListCreateView.as_view(), name="company-list"),
    path("<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
    path("<int:pk>/data-points/", CompanyDataPointListView.as_view(), name="company-datapoints"),
    path("<int:pk>/watchlist/", WatchListView.as_view(), name="company-watchlist"),
    path("<int:pk>/metrics/", CompanyMetricLatestView.as_view(), name="company-metrics"),
    path("<int:pk>/metrics/history/", CompanyMetricHistoryView.as_view(), name="company-metrics-history"),
    path("<int:pk>/metrics/export/", CompanyMetricExportView.as_view(), name="company-metrics-export"),
    path("alerts/", AlertListCreateView.as_view(), name="alert-list"),
]
