from rest_framework import serializers

from .models import Alert, Company, DataPoint, WatchList


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id", "name", "domain", "sector", "country", "description",
            "employee_count", "founded_year", "last_crawled_at",
            "crawl_frequency_hours", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_crawled_at"]


class DataPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataPoint
        fields = [
            "id", "company", "source_type", "source_url", "raw_text",
            "structured_json", "extracted_at", "confidence_score",
        ]
        read_only_fields = ["id"]


class WatchListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_domain = serializers.CharField(source="company.domain", read_only=True)

    class Meta:
        model = WatchList
        fields = ["id", "company", "company_name", "company_domain", "created_at"]
        read_only_fields = ["id", "created_at"]


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            "id", "company", "trigger_condition", "last_triggered_at",
            "delivery_channel", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at", "last_triggered_at"]
