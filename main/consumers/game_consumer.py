"""
WebSocket consumer для игровой сессии.
Обрабатывает события во время игры (смена вопроса, ответы игроков, завершение).
"""

import json
import logging

from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync

from main.models import GameSession

logger = logging.getLogger(__name__)


class GameConsumer(WebsocketConsumer):
    """
    WebSocket consumer для игровой сессии.

    Поддерживает две группы:
    - game_{pin} - все участники (игроки + хост)
    - game_host_{pin} - только хост (получает полную статистику)
    """

    def connect(self):
        """Подключение к WebSocket."""
        self.pin = self.scope['url_route']['kwargs']['pin']
        self.game_group_name = f'game_{self.pin}'
        self.host_group_name = f'game_host_{self.pin}'

        # Проверяем, что сессия существует
        try:
            session = GameSession.objects.get(pin=self.pin)
        except GameSession.DoesNotExist:
            logger.warning(f"Попытка подключения к несуществующей сессии: {self.pin}")
            self.close()
            return

        # Определяем, является ли пользователь хостом
        user = self.scope.get('user')
        is_host = user and user.is_authenticated and user.id == session.host_id

        # Добавляем в основную группу (все участники)
        async_to_sync(self.channel_layer.group_add)(
            self.game_group_name,
            self.channel_name
        )

        # Если это хост - добавляем также в группу хоста
        if is_host:
            async_to_sync(self.channel_layer.group_add)(
                self.host_group_name,
                self.channel_name
            )
            logger.info(f"Хост {user.username} подключился к game WebSocket: {self.pin}")
        else:
            username = user.username if user and user.is_authenticated else 'anonymous'
            logger.info(f"Игрок {username} подключился к game WebSocket: {self.pin}")

        self.accept()

    def disconnect(self, close_code):
        """Отключение от WebSocket."""
        # Удаляем из основной группы
        async_to_sync(self.channel_layer.group_discard)(
            self.game_group_name,
            self.channel_name
        )

        # Пытаемся удалить из группы хоста (если был добавлен)
        try:
            async_to_sync(self.channel_layer.group_discard)(
                self.host_group_name,
                self.channel_name
            )
        except Exception:
            pass

        logger.info(f"Отключение от game WebSocket: {self.pin}")

    def receive(self, text_data):
        """Получение сообщения от клиента."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            # Пока что клиенты не отправляют сообщения, только получают
            # Но оставляем для будущего расширения
            logger.debug(f"Получено сообщение от клиента: {message_type}")

        except json.JSONDecodeError:
            logger.warning(f"Некорректный JSON от клиента: {text_data}")

    # ===== Обработчики событий для всех участников =====

    def question_advanced(self, event):
        """Обработка события смены вопроса."""
        self.send(text_data=json.dumps({
            'type': 'question_advanced',
            'current_question': event['current_question'],
            'status': event['status']
        }))

    def game_finished(self, event):
        """Обработка события завершения игры."""
        self.send(text_data=json.dumps({
            'type': 'game_finished',
            'pin': event['pin']
        }))

    # ===== Обработчики событий только для хоста =====

    def game_state_update(self, event):
        """Обработка события обновления состояния игры (только для хоста)."""
        self.send(text_data=json.dumps({
            'type': 'game_state_update',
            'status': event.get('status'),
            'current_question': event.get('current_question'),
            'total_questions': event.get('total_questions'),
            'answered_count': event.get('answered_count'),
            'total_participants': event.get('total_participants'),
            'players': event.get('players', []),
            'current_question_text': event.get('current_question_text', ''),
            'current_options': event.get('current_options', []),
            'question_history': event.get('question_history', []),
            'ready_for_next_question': event.get('ready_for_next_question', False),
            'current_question_answers': event.get('current_question_answers', []),
            'time_remaining': event.get('time_remaining', 0),
        }))

    def player_answered(self, event):
        """Обработка события ответа игрока (только для хоста)."""
        self.send(text_data=json.dumps({
            'type': 'player_answered',
            'player_name': event['player_name'],
            'is_correct': event['is_correct']
        }))
