"""
ASGI config for quizziz_project.

Маршрутизирует HTTP через стандартное Django-приложение, а WebSocket —
через Channels с авторизацией по сессии Django.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quizziz_project.settings")

# get_asgi_application() инициализирует Django (apps registry) — вызываем
# до импорта потребителей, которые обращаются к моделям.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.main.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
