import uuid

from django.db import models

from core_api.apps.companies.models import Company


class ResearchReport(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="reports")
    requested_by_user_id = models.BigIntegerField(
        null=True, blank=True,
        help_text="User who triggered this report (auth-service user id)"
    )
    version = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    summary = models.TextField(blank=True)
    opportunities = models.JSONField(default=list)
    risks = models.JSONField(default=list)
    predictions = models.JSONField(default=list)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reports_researchreport"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self) -> str:
        return f"Report {self.id} — {self.company.name} [{self.status}]"

    def mark_running(self) -> None:
        self.status = self.STATUS_RUNNING
        self.save(update_fields=["status"])

    def mark_completed(self, summary: str, opportunities: list, risks: list,
                       predictions: list, confidence_score: float) -> None:
        from django.utils import timezone
        self.status = self.STATUS_COMPLETED
        self.summary = summary
        self.opportunities = opportunities
        self.risks = risks
        self.predictions = predictions
        self.confidence_score = confidence_score
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error: str) -> None:
        self.status = self.STATUS_FAILED
        self.error_message = error
        self.save(update_fields=["status", "error_message"])


class ReportSection(models.Model):
    SECTION_EXECUTIVE_SUMMARY = "executive_summary"
    SECTION_KEY_FINDINGS = "key_findings"
    SECTION_OPPORTUNITIES = "opportunities"
    SECTION_RISKS = "risks"
    SECTION_PREDICTIONS = "predictions"
    SECTION_METHODOLOGY = "methodology"
    SECTION_CHOICES = [
        (SECTION_EXECUTIVE_SUMMARY, "Executive Summary"),
        (SECTION_KEY_FINDINGS, "Key Findings"),
        (SECTION_OPPORTUNITIES, "Opportunities"),
        (SECTION_RISKS, "Risks"),
        (SECTION_PREDICTIONS, "Predictions"),
        (SECTION_METHODOLOGY, "Methodology"),
    ]

    report = models.ForeignKey(ResearchReport, on_delete=models.CASCADE, related_name="sections")
    section_type = models.CharField(max_length=50, choices=SECTION_CHOICES)
    content = models.TextField()
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "reports_reportsection"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["report", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.section_type} — Report {self.report_id}"
