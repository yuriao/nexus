import uuid

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core_api.apps.companies.models import Company

from .models import ResearchReport
from .serializers import ResearchReportSerializer, TriggerReportSerializer


class TriggerReportView(APIView):
    """POST /api/reports/trigger/ — scrape fresh data then run the agent analysis."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = TriggerReportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            company = Company.objects.get(pk=ser.validated_data["company_id"])
        except Company.DoesNotExist:
            return Response({"detail": "Company not found."}, status=status.HTTP_404_NOT_FOUND)

        # Determine version (latest + 1)
        last = ResearchReport.objects.filter(company=company).order_by("-version").first()
        version = (last.version + 1) if last else 1

        report = ResearchReport.objects.create(
            id=uuid.uuid4(),
            company=company,
            version=version,
            status=ResearchReport.STATUS_PENDING,
            requested_by_user_id=request.user.id,
        )

        # Dispatch: scraper first, then agent analysis as a chain
        # scraper-service task → agent-service task (runs after scrape completes)
        try:
            from celery import current_app
            from celery import chain

            scrape_task = current_app.signature(
                "tasks.run_company_scrape",
                kwargs={"company_id": company.id},
                queue="scraper",
                immutable=True,
            )
            agent_task = current_app.signature(
                "tasks.run_agent_analysis",
                kwargs={
                    "company_id": company.id,
                    "report_id": str(report.id),
                    "max_iterations": ser.validated_data["max_iterations"],
                    "model_name": ser.validated_data["model_name"],
                },
                queue="agent",
                immutable=True,
            )
            (scrape_task | agent_task).delay()

        except Exception as exc:
            report.mark_failed(f"Failed to enqueue task: {exc}")
            return Response(
                {"detail": f"Task dispatch failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        report.mark_running()
        return Response(ResearchReportSerializer(report).data, status=status.HTTP_202_ACCEPTED)


class ReportStatusView(generics.RetrieveAPIView):
    """GET /api/reports/{id}/status/ — lightweight status check."""

    permission_classes = [permissions.IsAuthenticated]
    queryset = ResearchReport.objects.all()
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        report = self.get_object()
        return Response(
            {
                "id": str(report.id),
                "status": report.status,
                "company": report.company.name,
                "version": report.version,
                "created_at": report.created_at,
                "completed_at": report.completed_at,
                "confidence_score": report.confidence_score,
            }
        )


class ReportDetailView(generics.RetrieveAPIView):
    """GET /api/reports/{id}/ — full report with sections."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResearchReportSerializer
    queryset = ResearchReport.objects.prefetch_related("sections").select_related("company")
    lookup_field = "id"


class ReportListView(generics.ListAPIView):
    """GET /api/reports/ — paginated list of reports, optionally filtered by company."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResearchReportSerializer

    def get_queryset(self):
        qs = ResearchReport.objects.select_related("company").prefetch_related("sections")
        company_id = self.request.query_params.get("company_id")
        status_filter = self.request.query_params.get("status")
        if company_id:
            qs = qs.filter(company_id=company_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-created_at")
