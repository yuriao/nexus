from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import APIKey
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — create a new user and return JWT tokens."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — obtain JWT token pair."""
    permission_classes = [permissions.AllowAny]


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh/ — refresh access token."""
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — retrieve or update current user."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class APIKeyListCreateView(APIView):
    """
    GET  /api/auth/api-keys/ — list API keys for current user
    POST /api/auth/api-keys/ — create a new API key (raw key shown once)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        keys = APIKey.objects.filter(user=request.user, is_active=True)
        return Response(APIKeySerializer(keys, many=True).data)

    def post(self, request):
        create_ser = APIKeyCreateSerializer(data=request.data)
        create_ser.is_valid(raise_exception=True)

        instance, raw_key = APIKey.create_for_user(
            user=request.user,
            name=create_ser.validated_data["name"],
            scopes=create_ser.validated_data["scopes"],
        )
        return Response(
            APIKeySerializer(instance, context={"raw_key": raw_key}).data,
            status=status.HTTP_201_CREATED,
        )


class APIKeyDestroyView(generics.DestroyAPIView):
    """DELETE /api/auth/api-keys/{id}/ — revoke an API key."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        key = self.get_object()
        key.is_active = False
        key.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
