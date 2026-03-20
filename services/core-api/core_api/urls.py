from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/companies/", include("core_api.apps.companies.urls")),
    path("api/reports/", include("core_api.apps.reports.urls")),
]
