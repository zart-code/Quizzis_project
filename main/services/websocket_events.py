"""
Сервис для публикации WebSocket-событий через Django Channels.

Предоставляет функции для отправки событий в группы каналов:
- Лобби: подключение игроков, кик, старт игры
- Игра: смена вопроса, ответы, завершение
"""

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)


def broadcast_player_joined(pin, player_data):
    """
    Уведомить всех участников лобби о подключении нового игрока.

    Args:
        pin: PIN-код игровой сессии
        player_data: словарь с данными игрока {id, username}
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"lobby_{pin}",
        {
            "type": "player_joined",
            "player": player_data,
        }
    )
    logger.info("WebSocket: игрок %s присоединился к лобби %s", player_data["username"], pin)


def broadcast_player_kicked(pin, player_id, player_name):
    """
    Уведомить всех участников лобби об исключении игрока.

    Args:
        pin: PIN-код игровой сессии
        player_id: ID исключённого игрока
        player_name: имя исключённого игрока
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"lobby_{pin}",
        {
            "type": "player_kicked",
            "player_id": player_id,
            "player_name": player_name,
        }
    )
    logger.info("WebSocket: игрок %s (ID: %d) исключён из лобби %s", player_name, player_id, pin)


def broadcast_lobby_locked(pin, is_locked):
    """
    Уведомить всех участников лобби об изменении статуса закрытия.

    Args:
        pin: PIN-код игровой сессии
        is_locked: True если лобби закрыто, False если открыто
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"lobby_{pin}",
        {
            "type": "lobby_locked",
            "is_locked": is_locked,
        }
    )
    logger.info("WebSocket: лобби %s %s", pin, "закрыто" if is_locked else "открыто")


def broadcast_game_started(pin):
    """
    Уведомить всех участников лобби о начале игры.

    Args:
        pin: PIN-код игровой сессии
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"lobby_{pin}",
        {
            "type": "game_started",
            "pin": pin,
        }
    )
    logger.info("WebSocket: игра начата в лобби %s", pin)


def broadcast_session_deleted(pin):
    """
    Уведомить всех участников об удалении сессии.

    Args:
        pin: PIN-код удалённой сессии
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"lobby_{pin}",
        {
            "type": "session_deleted",
            "pin": pin,
        }
    )
    logger.info("WebSocket: сессия %s удалена", pin)


def broadcast_question_advanced(pin, current_question, status):
    """
    Уведомить всех игроков о переключении на следующий вопрос.

    Args:
        pin: PIN-код игровой сессии
        current_question: номер текущего вопроса
        status: статус сессии (in_progress, finished)
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{pin}",
        {
            "type": "question_advanced",
            "current_question": current_question,
            "status": status,
        }
    )
    logger.info("WebSocket: переключение на вопрос %d в сессии %s", current_question, pin)


def broadcast_game_state_update(pin, game_state):
    """
    Отправить обновлённое состояние игры хосту (для отображения статистики).

    Args:
        pin: PIN-код игровой сессии
        game_state: словарь с полным состоянием игры
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_host_{pin}",
        {
            "type": "game_state_update",
            **game_state
        }
    )


def broadcast_game_finished(pin):
    """
    Уведомить всех игроков о завершении игры.

    Args:
        pin: PIN-код игровой сессии
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{pin}",
        {
            "type": "game_finished",
            "pin": pin,
        }
    )
    logger.info("WebSocket: игра завершена в сессии %s", pin)


def broadcast_player_answered(pin, player_name, is_correct):
    """
    Уведомить хоста о том, что игрок ответил на текущий вопрос.

    Args:
        pin: PIN-код игровой сессии
        player_name: имя игрока
        is_correct: True если ответ верный
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_host_{pin}",
        {
            "type": "player_answered",
            "player_name": player_name,
            "is_correct": is_correct,
        }
    )
    logger.debug("WebSocket: игрок %s ответил в сессии %s (верно: %s)", player_name, pin, is_correct)
