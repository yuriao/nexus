"""
Metrics API views — retrieve, list, and export company metrics.
Endpoints:
  GET /api/companies/<id>/metrics/           — latest metrics for a company
  GET /api/companies/<id>/metrics/history/   — all snapshots over time (time-series)
  GET /api/companies/<id>/metrics/export/    — export as CSV or JSON for packaging/API sale
"""
from datetime import datetime, timezone

from django.http import HttpResponse
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core_api.apps.companies.models import Company, CompanyMetric


class CompanyMetricSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = CompanyMetric
        fields = [
            "id", "metric_code", "metric_name", "unit",
            "value", "confidence", "source", "note", "calculated_at",
        ]

    def get_value(self, obj):
        if obj.value is None:
            return None
        return float(obj.value)


class CompanyMetricLatestView(APIView):
    """GET /api/companies/<pk>/metrics/ — latest snapshot of all 20 metrics."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get the most recent calculated_at timestamp
        latest = CompanyMetric.objects.filter(company=company).order_by("-calculated_at").first()
        if not latest:
            return Response({
                "company_id": pk,
                "company_name": company.name,
                "calculated_at": None,
                "metrics": [],
            })

        metrics = CompanyMetric.objects.filter(
            company=company,
            calculated_at=latest.calculated_at,
        ).order_by("metric_code")

        return Response({
            "company_id": pk,
            "company_name": company.name,
            "domain": company.domain,
            "calculated_at": latest.calculated_at.isoformat(),
            "metrics": CompanyMetricSerializer(metrics, many=True).data,
        })


class CompanyMetricHistoryView(APIView):
    """GET /api/companies/<pk>/metrics/history/?metric=M01 — time-series for one metric."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        metric_code = request.query_params.get("metric", "M01")
        limit = int(request.query_params.get("limit", 20))

        history = CompanyMetric.objects.filter(
            company=company,
            metric_code=metric_code,
        ).order_by("-calculated_at")[:limit]

        return Response({
            "company_id": pk,
            "company_name": company.name,
            "metric_code": metric_code,
            "history": CompanyMetricSerializer(history, many=True).data,
        })


class CompanyMetricExportView(APIView):
    """GET /api/companies/<pk>/metrics/export/?format=csv|json — export for packaging/API."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        fmt = request.query_params.get("format", "json")
        latest = CompanyMetric.objects.filter(company=company).order_by("-calculated_at").first()
        if not latest:
            return Response({"detail": "No metrics available."}, status=404)

        metrics = CompanyMetric.objects.filter(
            company=company,
            calculated_at=latest.calculated_at,
        ).order_by("metric_code")

        if fmt == "csv":
            import csv
            import io
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["company_id", "company_name", "domain", "calculated_at",
                             "metric_code", "metric_name", "unit", "value", "confidence", "source", "note"])
            for m in metrics:
                writer.writerow([
                    pk, company.name, company.domain,
                    latest.calculated_at.isoformat(),
                    m.metric_code, m.metric_name, m.unit,
                    float(m.value) if m.value is not None else "",
                    m.confidence, m.source, m.note,
                ])
            response = HttpResponse(buf.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{company.domain}_metrics.csv"'
            return response

        # JSON export (default) — API-ready format
        data = {
            "schema_version": "1.0",
            "provider": "Nexus Intelligence",
            "company": {
                "id": pk,
                "name": company.name,
                "domain": company.domain,
            },
            "calculated_at": latest.calculated_at.isoformat(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "metrics": CompanyMetricSerializer(metrics, many=True).data,
        }
        return Response(data)
