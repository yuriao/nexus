from rest_framework import serializers

from .models import ReportSection, ResearchReport


class ReportSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSection
        fields = ["id", "section_type", "content", "sort_order"]


class ResearchReportSerializer(serializers.ModelSerializer):
    sections = ReportSectionSerializer(many=True, read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = ResearchReport
        fields = [
            "id", "company", "company_name", "version", "status",
            "summary", "opportunities", "risks", "predictions",
            "confidence_score", "error_message",
            "created_at", "completed_at", "sections",
        ]
        read_only_fields = [
            "id", "version", "status", "summary", "opportunities", "risks",
            "predictions", "confidence_score", "error_message",
            "created_at", "completed_at", "sections",
        ]


class TriggerReportSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    max_iterations = serializers.IntegerField(default=3, min_value=1, max_value=10)
    model_name = serializers.CharField(default="moonshot-v1-8k")
