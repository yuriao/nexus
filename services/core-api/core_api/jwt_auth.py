"""
core_api/jwt_auth.py — Stateless JWT authentication for microservice.
Validates the token using the shared SECRET_KEY but does NOT look up a
local User row.  Instead it returns a lightweight TokenUser whose id,
email and is_authenticated come directly from the JWT payload.
"""
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class TokenUser:
    """Minimal user-like object built from JWT claims (no DB hit)."""

    is_anonymous = False
    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, payload):
        self.id = payload.get("user_id")
        self.pk = self.id
        self.email = payload.get("email", "")
        self.username = payload.get("username", str(self.id))

    def __str__(self):
        return self.username


class StatelessJWTAuthentication(JWTAuthentication):
    """
    Drop-in replacement for JWTAuthentication that skips the DB user lookup.
    Works with tokens issued by any service that shares the same SECRET_KEY.
    """

    def get_user(self, validated_token):
        try:
            return TokenUser(validated_token)
        except Exception:
            raise InvalidToken("Token contained no recognisable user identification")
