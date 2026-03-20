import hashlib
import os
import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model. Uses email as the unique identifier for JWT."""

    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "accounts_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.email


class APIKey(models.Model):
    """Hashed API key for service-to-service or programmatic access."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    scopes = models.JSONField(default=list, help_text='e.g. ["companies:read", "reports:write"]')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "accounts_apikey"
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} — {self.name}"

    @classmethod
    def generate(cls) -> str:
        """Generate a new raw key (prefix + random). Returns raw key — store this once."""
        return "nxk_" + secrets.token_urlsafe(32)

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """SHA-256 hash of the raw key for storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def create_for_user(cls, user: User, name: str, scopes: list[str]) -> tuple["APIKey", str]:
        """Create a new APIKey and return (instance, raw_key). Raw key is shown once."""
        raw_key = cls.generate()
        instance = cls.objects.create(
            user=user,
            key_hash=cls.hash_key(raw_key),
            name=name,
            scopes=scopes,
        )
        return instance, raw_key
