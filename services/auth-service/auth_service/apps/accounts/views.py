from django.contrib.auth import authenticate, get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

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


class LoginView(APIView):
    """
    POST /api/auth/login/
    Accepts { username, password } or { email, password }.
    Since USERNAME_FIELD=email, we resolve username → email then authenticate.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get("username") or request.data.get("email", "")
        password = request.data.get("password", "")

        if not identifier or not password:
            return Response(
                {"detail": "username/email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # USERNAME_FIELD is email — so authenticate() expects email as username kwarg
        # First try treating identifier as email directly
        user = authenticate(request, username=identifier, password=password)

        # If that fails, try looking up by username field → get their email
        if user is None:
            try:
                u = User.objects.get(username=identifier)
                user = authenticate(request, username=u.email, password=password)
            except User.DoesNotExist:
                pass

        if user is None or not user.is_active:
            return Response(
                {"detail": "No active account found with the given credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        })


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
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        key = self.get_object()
        key.is_active = False
        key.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
