from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    sector = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    employee_count = models.IntegerField(null=True, blank=True)
    founded_year = models.SmallIntegerField(null=True, blank=True)
    last_crawled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    crawl_frequency_hours = models.IntegerField(default=24)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "companies_company"
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.domain})"


class DataPoint(models.Model):
    SOURCE_NEWS = "news"
    SOURCE_JOBS = "jobs"
    SOURCE_CRUNCHBASE = "crunchbase"
    SOURCE_LINKEDIN = "linkedin"
    SOURCE_CUSTOM = "custom"
    SOURCE_CHOICES = [
        (SOURCE_NEWS, "News"),
        (SOURCE_JOBS, "Jobs"),
        (SOURCE_CRUNCHBASE, "Crunchbase"),
        (SOURCE_LINKEDIN, "LinkedIn"),
        (SOURCE_CUSTOM, "Custom"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="data_points")
    source_type = models.CharField(max_length=50, choices=SOURCE_CHOICES, db_index=True)
    source_url = models.TextField()
    raw_text = models.TextField()
    structured_json = models.JSONField(null=True, blank=True)
    extracted_at = models.DateTimeField(db_index=True)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3, default=1.000)

    class Meta:
        db_table = "companies_datapoint"
        ordering = ["-extracted_at"]
        indexes = [
            models.Index(fields=["company", "source_type"]),
        ]

    def __str__(self) -> str:
        return f"[{self.source_type}] {self.company.name} @ {self.extracted_at:%Y-%m-%d}"


class WatchList(models.Model):
    user_id = models.BigIntegerField(db_index=True, help_text="References auth-service user id")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="watchers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "companies_watchlist"
        unique_together = [("user_id", "company")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"user:{self.user_id} → {self.company.name}"


class Alert(models.Model):
    DELIVERY_EMAIL = "email"
    DELIVERY_WEBHOOK = "webhook"
    DELIVERY_SLACK = "slack"
    DELIVERY_CHOICES = [
        (DELIVERY_EMAIL, "Email"),
        (DELIVERY_WEBHOOK, "Webhook"),
        (DELIVERY_SLACK, "Slack"),
    ]

    id = models.UUIDField(primary_key=True)
    user_id = models.BigIntegerField(db_index=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="alerts")
    trigger_condition = models.JSONField(
        help_text='e.g. {"type": "new_data", "source_type": "jobs"}'
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    delivery_channel = models.CharField(max_length=50, choices=DELIVERY_CHOICES, default=DELIVERY_EMAIL)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "companies_alert"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Alert for {self.company.name} → {self.user_id}"
