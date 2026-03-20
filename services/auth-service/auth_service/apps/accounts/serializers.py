from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import APIKey

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "username", "password", "password2", "first_name", "last_name"]
        read_only_fields = ["id"]

    def validate(self, data: dict) -> dict:
        if data["password"] != data.pop("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return data

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "date_joined", "is_active"]
        read_only_fields = ["id", "date_joined"]


class APIKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    scopes = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        help_text='e.g. ["companies:read", "reports:write"]',
    )


class APIKeySerializer(serializers.ModelSerializer):
    # raw_key is only present on creation response
    raw_key = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = [
            "id", "name", "scopes", "created_at", "last_used_at",
            "is_active", "raw_key",
        ]
        read_only_fields = fields

    def get_raw_key(self, obj: APIKey) -> str | None:
        return self.context.get("raw_key")
