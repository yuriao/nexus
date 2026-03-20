from django.urls import path

from .views import (
    APIKeyDestroyView,
    APIKeyListCreateView,
    LoginView,
    MeView,
    RefreshView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("api-keys/", APIKeyListCreateView.as_view(), name="apikey-list-create"),
    path("api-keys/<int:pk>/", APIKeyDestroyView.as_view(), name="apikey-destroy"),
]
