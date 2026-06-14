"""Тесты WebSocket-потребителя лобби (LobbyConsumer).

Используют in-memory channel layer (включается автоматически в тестах).
Проверяют, что после подключения клиент получает стартовый снимок, а
события из views доставляются в реальном времени.
"""

from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from apps.quiz.models import GameSession
from apps.quiz_game.models import Quiz
from apps.main.routing import websocket_urlpatterns
from apps.main.services import realtime

# Приложение без AllowedHostsOriginValidator/AuthMiddleware — пользователя
# и сессию подкладываем в scope вручную, как это сделал бы middleware.
test_application = URLRouter(websocket_urlpatterns)


class LobbyConsumerTest(TransactionTestCase):
    """Проверка базового WebSocket-сценария лобби."""

    fixtures = ["db.json"]

    def setUp(self):
        self.teacher = User.objects.get(pk=2)
        self.quiz = Quiz.objects.get(pk=1)
        self.session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="555000",
            status=GameSession.WAITING,
        )

    async def _connect(self, user=None):
        communicator = WebsocketCommunicator(
            test_application, f"/ws/lobby/{self.session.pin}/"
        )
        # Имитация AuthMiddleware: подкладываем пользователя и сессию.
        from django.contrib.auth.models import AnonymousUser

        communicator.scope["user"] = user if user is not None else AnonymousUser()
        communicator.scope.setdefault("session", {})
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_host_receives_player_list_snapshot(self):
        """Хост при подключении получает снимок списка игроков."""
        communicator, connected = await self._connect(user=self.teacher)
        self.assertTrue(connected)

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "player_list")
        self.assertEqual(response["count"], 0)

        await communicator.disconnect()

    async def test_player_receives_state_snapshot(self):
        """Игрок (аноним) при подключении получает снимок состояния."""
        communicator, connected = await self._connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "player_state")
        self.assertEqual(response["status"], GameSession.WAITING)

        await communicator.disconnect()

    async def test_game_started_broadcast_reaches_player(self):
        """Событие game_started доставляется подключённому игроку."""
        communicator, connected = await self._connect()
        self.assertTrue(connected)
        # Стартовый снимок.
        await communicator.receive_json_from(timeout=2)

        # Публикуем событие старта игры (как это делает start_game_view).
        await database_sync_to_async(realtime.broadcast_game_started)(
            self.session.pin
        )

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "game_started")

        await communicator.disconnect()

    async def test_connect_to_missing_session_rejected(self):
        """Подключение к несуществующему PIN отклоняется."""
        communicator = WebsocketCommunicator(test_application, "/ws/lobby/000000/")
        from django.contrib.auth.models import AnonymousUser

        communicator.scope["user"] = AnonymousUser()
        communicator.scope.setdefault("session", {})
        connected, _ = await communicator.connect()
        self.assertFalse(connected)


class AdminConsumerTest(TransactionTestCase):
    """Проверка WebSocket-канала админ-панели."""

    fixtures = ["db.json"]

    def setUp(self):
        self.admin = User.objects.create_user(username="admin")  # станет admin
        # Сигнал делает username=='admin' администратором.
        self.admin.refresh_from_db()
        self.student = User.objects.get(pk=1)

    async def _connect(self, user):
        communicator = WebsocketCommunicator(test_application, "/ws/admin/")
        communicator.scope["user"] = user
        communicator.scope.setdefault("session", {})
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_admin_receives_snapshot(self):
        """Админ при подключении получает снимок данных панели."""
        communicator, connected = await self._connect(self.admin)
        self.assertTrue(connected)

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "admin_update")
        self.assertIn("stats", response)
        self.assertIn("users", response)
        self.assertIn("quizzes", response)

        await communicator.disconnect()

    async def test_non_admin_rejected(self):
        """Не-админ не может подключиться к каналу админ-панели."""
        communicator, connected = await self._connect(self.student)
        self.assertFalse(connected)

    async def test_admin_update_broadcast(self):
        """Событие broadcast_admin_update доставляет свежий снимок."""
        communicator, connected = await self._connect(self.admin)
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=2)  # стартовый снимок

        await database_sync_to_async(realtime.broadcast_admin_update)()

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "admin_update")

        await communicator.disconnect()

    async def test_quiz_creation_pushes_update_to_admin(self):
        """Создание квиза ОБЫЧНЫМ пользователем мгновенно обновляет админку.

        Это ключевой сценарий: админ ничего не делает, но видит новый квиз
        без перезагрузки страницы — событие приходит через сигнал модели.
        """
        communicator, connected = await self._connect(self.admin)
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=2)  # стартовый снимок

        # Обычный пользователь создаёт квиз (как из обычной формы).
        @database_sync_to_async
        def create_quiz():
            from apps.main.models import Quiz

            return Quiz.objects.create(title="Новый квиз", creator=self.student)

        await create_quiz()

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "admin_update")
        titles = [q["title"] for q in response["quizzes"]]
        self.assertIn("Новый квиз", titles)

        await communicator.disconnect()
