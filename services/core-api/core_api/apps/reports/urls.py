from django.urls import path

from .views import ReportDetailView, ReportListView, ReportStatusView, TriggerReportView

urlpatterns = [
    path("", ReportListView.as_view(), name="report-list"),
    path("trigger/", TriggerReportView.as_view(), name="report-trigger"),
    path("<uuid:id>/", ReportDetailView.as_view(), name="report-detail"),
    path("<uuid:id>/status/", ReportStatusView.as_view(), name="report-status"),
]
