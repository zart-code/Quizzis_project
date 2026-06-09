"""
WebSocket consumer для лобби: обработка real-time событий
(подключение игроков, кик, старт игры, закрытие лобби).
"""

import json
import logging
from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from main.models import GameSession, GameParticipant

logger = logging.getLogger(__name__)


class LobbyConsumer(WebsocketConsumer):
    """Consumer для WebSocket-соединений в лобби."""

    def connect(self):
        """Подключение клиента к WebSocket-каналу лобби."""
        self.pin = self.scope["url_route"]["kwargs"]["pin"]
        self.lobby_group_name = f"lobby_{self.pin}"

        # Проверяем существование сессии
        session = GameSession.objects.filter(pin=self.pin).first()
        if session is None:
            self.close()
            return

        # Добавляем канал в группу лобби
        async_to_sync(self.channel_layer.group_add)(
            self.lobby_group_name,
            self.channel_name,
        )

        # Если подключился хост — добавляем в отдельную группу
        user = self.scope.get("user")
        if user and user.is_authenticated and session.host == user:
            self.host_group_name = f"lobby_host_{self.pin}"
            async_to_sync(self.channel_layer.group_add)(
                self.host_group_name,
                self.channel_name,
            )
        else:
            self.host_group_name = None

        self.accept()
        logger.info(
            "WebSocket подключение к лобби %s: пользователь %s",
            self.pin,
            user.username if user and user.is_authenticated else "anonymous",
        )

    def disconnect(self, close_code):
        """Отключение клиента от WebSocket-канала лобби."""
        async_to_sync(self.channel_layer.group_discard)(
            self.lobby_group_name,
            self.channel_name,
        )

        if self.host_group_name:
            async_to_sync(self.channel_layer.group_discard)(
                self.host_group_name,
                self.channel_name,
            )

        logger.info(
            "WebSocket отключение от лобби %s (код: %s)",
            self.pin,
            close_code,
        )

    def receive(self, text_data=None, bytes_data=None):
        """Обработка входящего сообщения от клиента."""
        if text_data is None:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.warning(
                "Некорректный JSON от клиента в лобби %s", self.pin
            )
            return

        action = data.get("action")
        logger.debug(
            "WebSocket сообщение в лобби %s: action=%s", self.pin, action
        )

    # --- Обработчики событий, отправляемых через channel_layer --- #

    def player_joined(self, event):
        """Отправка клиенту события: новый игрок присоединился к лобби."""
        self.send(text_data=json.dumps({
            "type": "player_joined",
            "player": event["player"],
        }))

    def player_kicked(self, event):
        """Отправка клиенту события: игрок был выгнан из лобби."""
        self.send(text_data=json.dumps({
            "type": "player_kicked",
            "player_id": event["player_id"],
            "player_name": event["player_name"],
        }))

    def lobby_locked(self, event):
        """Отправка клиенту события: лобби закрыто/открыто."""
        self.send(text_data=json.dumps({
            "type": "lobby_locked",
            "is_locked": event["is_locked"],
        }))

    def game_started(self, event):
        """Отправка клиенту события: игра началась."""
        self.send(text_data=json.dumps({
            "type": "game_started",
            "pin": event["pin"],
        }))

    def session_deleted(self, event):
        """Отправка клиенту события: сессия была удалена."""
        self.send(text_data=json.dumps({
            "type": "session_deleted",
            "pin": event["pin"],
        }))