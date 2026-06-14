"""WebSocket-потребитель для админ-панели.

Заменяет HTTP-polling (`api_admin_stats`, `api_admin_users`,
`api_admin_quizzes`), который раньше опрашивал сервер каждые 3 секунды.
Теперь админ держит одно соединение и получает свежий снимок данных
только при реальных изменениях (бан, смена роли, удаление квиза и т.д.).
"""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.main.services import realtime


class AdminConsumer(AsyncJsonWebsocketConsumer):
    """Real-time канал для панели администратора."""

    async def connect(self):
        user = self.scope.get("user")
        if not await self._is_admin(user):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(realtime.ADMIN_GROUP, self.channel_name)
        await self.accept()

        # Стартовый снимок сразу после подключения.
        await self.send_json(await self._snapshot())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            realtime.ADMIN_GROUP, self.channel_name
        )

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "sync":
            await self.send_json(await self._snapshot())

    async def admin_changed(self, event):
        """Данные изменились — рассылаем свежий снимок."""
        await self.send_json(await self._snapshot())

    @database_sync_to_async
    def _is_admin(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return False
        profile = getattr(user, "profile", None)
        return bool(profile and profile.is_admin)

    @database_sync_to_async
    def _snapshot(self):
        return realtime.build_admin_snapshot()
