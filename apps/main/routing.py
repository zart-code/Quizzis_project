"""WebSocket URL-маршруты проекта."""

from django.urls import re_path

from apps.superuser_app.consumers.admin_consumer import AdminConsumer
from apps.game_lobby.consumers.lobby_consumer import LobbyConsumer

websocket_urlpatterns = [
    # Единый канал на лобби/сессию по PIN. Хост и игроки используют один и
    # тот же эндпоинт, роль определяется на стороне сервера.
    re_path(r"^ws/lobby/(?P<pin>\w+)/$", LobbyConsumer.as_asgi()),
    # Канал админ-панели (real-time статистика, пользователи, квизы).
    re_path(r"^ws/admin/$", AdminConsumer.as_asgi()),
]
