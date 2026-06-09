"""
WebSocket URL routing для Django Channels.

Определяет маршруты для WebSocket-соединений:
- /ws/lobby/{pin}/       — лобби (ожидание, игроки, хост)
- /ws/game/{pin}/        — игровая сессия (вопросы, ответы, таймер)
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/lobby/(?P<pin>[0-9]{6})/$",
        consumers.lobby_consumer.LobbyConsumer.as_asgi(),
    ),
    re_path(
        r"ws/game/(?P<pin>[0-9]{6})/$",
        consumers.game_consumer.GameConsumer.as_asgi(),
    ),
]