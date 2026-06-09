"""
WebSocket consumer для игровой сессии: обработка смены вопроса,
ответов игроков, завершения игры.
"""

import json
import logging
from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from main.models import GameSession, GameParticipant

logger = logging.getLogger(__name__)


class GameConsumer(WebsocketConsumer):
    """Consumer для WebSocket-соединений во время активной игры."""

    def connect(self):
        """Подключение клиента к WebSocket-каналу игры."""
        self.pin = self.scope["url_route"]["kwargs"]["pin"]
        self.game_group_name = f"game_{self.pin}"

        # Проверяем существование сессии
        session = GameSession.objects.filter(pin=self.pin).first()
        if session is None:
            self.close()
            return

        # Добавляем канал в группу игры
        async_to_sync(self.channel_layer.group_add)(
            self.game_group_name,
            self.channel_name,
        )

        # Если подключился хост — добавляем в отдельную хостовую группу
        user = self.scope.get("user")
        if user and user.is_authenticated and session.host == user:
            self.host_game_group_name = f"game_host_{self.pin}"
            async_to_sync(self.channel_layer.group_add)(
                self.host_game_group_name,
                self.channel_name,
            )
        else:
            self.host_game_group_name = None

        self.accept()
        logger.info(
            "WebSocket подключение к игре %s: пользователь %s",
            self.pin,
            user.username if user and user.is_authenticated else "anonymous",
        )

    def disconnect(self, close_code):
        """Отключение клиента от WebSocket-канала игры."""
        async_to_sync(self.channel_layer.group_discard)(
            self.game_group_name,
            self.channel_name,
        )

        if self.host_game_group_name:
            async_to_sync(self.channel_layer.group_discard)(
                self.host_game_group_name,
                self.channel_name,
            )

        logger.info(
            "WebSocket отключение от игры %s (код: %s)",
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
                "Некорректный JSON от клиента в игре %s", self.pin
            )
            return

        action = data.get("action")
        logger.debug(
            "WebSocket сообщение в игре %s: action=%s", self.pin, action
        )

    # --- Обработчики событий, отправляемых через channel_layer --- #

    def game_state_update(self, event):
        """Отправка клиенту обновлённого состояния игры (только хосту)."""
        self.send(text_data=json.dumps({
            "type": "game_state_update",
            "status": event.get("status"),
            "current_question": event.get("current_question"),
            "total_questions": event.get("total_questions"),
            "answered_count": event.get("answered_count"),
            "total_participants": event.get("total_participants"),
            "players": event.get("players", []),
            "current_question_text": event.get("current_question_text", ""),
            "current_options": event.get("current_options", []),
            "question_history": event.get("question_history", []),
            "ready_for_next_question": event.get("ready_for_next_question", False),
            "current_question_answers": event.get("current_question_answers", []),
            "time_remaining": event.get("time_remaining", 0),
        }))

    def question_advanced(self, event):
        """Отправка клиенту события: учитель переключил вопрос."""
        self.send(text_data=json.dumps({
            "type": "question_advanced",
            "current_question": event["current_question"],
            "status": event.get("status"),
        }))

    def game_finished(self, event):
        """Отправка клиенту события: игра завершена."""
        self.send(text_data=json.dumps({
            "type": "game_finished",
            "pin": event["pin"],
        }))

    def player_answered(self, event):
        """Отправка хосту события: игрок ответил на текущий вопрос."""
        self.send(text_data=json.dumps({
            "type": "player_answered",
            "player_name": event["player_name"],
            "is_correct": event["is_correct"],
        }))