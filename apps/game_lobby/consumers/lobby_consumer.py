"""WebSocket-потребитель для лобби и игровых сессий.

Один эндпоинт обслуживает и хоста, и игроков. Роль определяется на
сервере: если авторизованный пользователь является хостом сессии — он
получает данные дашборда (список игроков / статистику), иначе клиент
считается игроком и получает своё состояние сессии.

Вместо постоянного HTTP-polling клиент держит одно WebSocket-соединение
и получает push-уведомления только когда что-то реально изменилось.
"""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.quiz.models import GameSession
from apps.main.services import realtime


class LobbyConsumer(AsyncJsonWebsocketConsumer):
    """Канал реального времени для одной игровой сессии (по PIN)."""

    async def connect(self):
        self.pin = self.scope["url_route"]["kwargs"]["pin"]
        self.group_name = realtime.lobby_group(self.pin)

        session_info = await self._load_session_info()
        if session_info is None:
            # Нет такой сессии — закрываем соединение.
            await self.close(code=4404)
            return

        self.is_host = session_info["is_host"]
        self.participant_id = session_info["participant_id"]

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Отправляем стартовый снимок состояния сразу после подключения,
        # чтобы клиент не ждал первого события.
        await self._send_snapshot()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Клиент может попросить актуальный снимок (например, при reconnect)."""
        if content.get("action") == "sync":
            await self._send_snapshot()

    # ------------------------------------------------------------------
    # Обработчики событий из группы (group_send type -> метод)
    # ------------------------------------------------------------------
    async def lobby_changed(self, event):
        if self.is_host:
            await self.send_json(await self._host_lobby_payload())

    async def player_kicked(self, event):
        if self.is_host:
            await self.send_json(await self._host_lobby_payload())
        elif event.get("participant_id") == self.participant_id:
            await self.send_json({"type": "kicked"})

    async def game_started(self, event):
        if self.is_host:
            await self.send_json(await self._host_stats_payload())
        else:
            await self.send_json({"type": "game_started"})

    async def question_advanced(self, event):
        if self.is_host:
            await self.send_json(await self._host_stats_payload())
        else:
            await self.send_json(await self._player_payload())

    async def stats_changed(self, event):
        if self.is_host:
            await self.send_json(await self._host_stats_payload())
        else:
            await self.send_json(await self._player_payload())

    # ------------------------------------------------------------------
    # Снимок состояния по роли
    # ------------------------------------------------------------------
    async def _send_snapshot(self):
        if self.is_host:
            status = await self._session_status()
            if status == GameSession.WAITING:
                await self.send_json(await self._host_lobby_payload())
            else:
                await self.send_json(await self._host_stats_payload())
        else:
            await self.send_json(await self._player_payload())

    # ------------------------------------------------------------------
    # Payload builders (через ORM в отдельном потоке)
    # ------------------------------------------------------------------
    @database_sync_to_async
    def _load_session_info(self):
        try:
            session = GameSession.objects.select_related("host").get(pin=self.pin)
        except GameSession.DoesNotExist:
            return None

        user = self.scope.get("user")
        is_host = bool(
            user
            and getattr(user, "is_authenticated", False)
            and session.host_id == user.id
        )

        participant_id = None
        if not is_host:
            session_store = self.scope.get("session")
            if session_store is not None:
                participant_id = session_store.get(f"lobby_participant_{self.pin}")

        return {"is_host": is_host, "participant_id": participant_id}

    @database_sync_to_async
    def _session_status(self):
        return (
            GameSession.objects.filter(pin=self.pin)
            .values_list("status", flat=True)
            .first()
        )

    @database_sync_to_async
    def _host_lobby_payload(self):
        session = GameSession.objects.get(pin=self.pin)
        data = realtime.build_player_list(session)
        data["type"] = "player_list"
        return data

    @database_sync_to_async
    def _host_stats_payload(self):
        session = GameSession.objects.get(pin=self.pin)
        data = realtime.build_game_stats(session)
        data["type"] = "game_stats"
        return data

    @database_sync_to_async
    def _player_payload(self):
        session = GameSession.objects.get(pin=self.pin)
        data = realtime.build_player_state(session, self.participant_id)
        data["type"] = "player_state"
        return data
