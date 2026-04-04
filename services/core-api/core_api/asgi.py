"""
ASGI config for core-api.
Enables Django Channels with HTTP + WebSocket routing.
"""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_api.settings")

# Initialize Django ASGI application early to ensure the AppRegistry is populated
# before importing channels modules.
django_asgi_app = get_asgi_application()

from core_api.apps.ws.consumers import ReportConsumer  # noqa: E402

websocket_urlpatterns = [
    path("ws/reports/<str:report_id>/", ReportConsumer.as_asgi()),
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
