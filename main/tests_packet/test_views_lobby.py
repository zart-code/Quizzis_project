"""Тесты для представлений лобби (views_lobby.py)."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from main.models import Quiz, GameSession, GameParticipant, GameAnswer, QuizResult
from main.services.quiz_revisions import get_current_revision


class LobbyViewsTest(TestCase):
    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.get(pk=2)
        self.student = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)  # активный
        self.session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="123456",
            status=GameSession.WAITING,
            is_locked=False,
        )

    # --- create_lobby_view ---
    def test_create_lobby_view(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("create_lobby", args=[self.quiz.id]))
        self.assertRedirects(
            response, reverse("my_quizzes"), fetch_redirect_response=False
        )
        session = GameSession.objects.filter(quiz=self.quiz, host=self.teacher).last()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_create_lobby_for_draft_quiz(self):
        draft_quiz = Quiz.objects.create(
            title="Draft", creator=self.teacher, status=Quiz.DRAFT
        )
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("create_lobby", args=[draft_quiz.id]))
        self.assertRedirects(
            response, reverse("my_quizzes"), fetch_redirect_response=False
        )

    # --- lobby_view (для хоста) ---
    def test_lobby_view_get(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["session"], self.session)

    def test_lobby_view_non_host(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 404)

    # --- toggle_lock_view ---
    def test_toggle_lock_view(self):
        self.client.force_login(self.teacher)
        self.assertFalse(self.session.is_locked)
        response = self.client.post(reverse("toggle_lock", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_locked)

    # --- delete_session_view ---
    def test_delete_session_view(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("delete_session", args=[self.session.pin]))
        self.assertRedirects(
            response, reverse("my_quizzes"), fetch_redirect_response=False
        )
        with self.assertRaises(GameSession.DoesNotExist):
            self.session.refresh_from_db()

    # --- api_players_view (для хоста) ---
    def test_api_players_view(self):
        self.client.force_login(self.teacher)
        # Добавляем участника
        GameParticipant.objects.create(session=self.session, user=self.student)
        response = self.client.get(reverse("api_players", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("players", data)
        self.assertEqual(len(data["players"]), 1)
        self.assertEqual(data["players"][0]["username"], self.student.username)
        self.assertFalse(data["is_locked"])

    # --- join_lobby_view (для игрока) ---
    def test_join_lobby_view_success(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "join_lobby.html")
        self.assertTrue(
            GameParticipant.objects.filter(
                session=self.session, user=self.student
            ).exists()
        )

    def test_join_lobby_view_when_already_joined(self):
        GameParticipant.objects.create(session=self.session, user=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            GameParticipant.objects.filter(
                session=self.session, user=self.student
            ).count(),
            1,
        )

    def test_join_lobby_view_host_redirect(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("join_lobby", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))

    # --- api_state_view (требует авторизации?) ---
    def test_api_state_view(self):
        # В проекте, вероятно, глобальная авторизация – залогиним пользователя
        self.client.force_login(self.student)
        response = self.client.get(reverse("api_state", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], self.session.status)

    # --- start_game_view ---
    def test_start_game_view_with_participants(self):
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(session=self.session, user=self.student)
        response = self.client.post(reverse("start_game", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "in_progress")

    def test_start_game_view_no_participants(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("start_game", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertNotEqual(self.session.status, "in_progress")

    def test_start_game_when_already_started(self):
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(session=self.session, user=self.student)
        self.session.status = "in_progress"
        self.session.save()
        response = self.client.post(reverse("start_game", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "in_progress")  # статус не изменился

    # --- session_play_view (игровой процесс) ---
    def test_session_play_view_redirect_if_not_started(self):
        self.client.force_login(self.student)
        GameParticipant.objects.create(session=self.session, user=self.student)
        response = self.client.get(reverse("session_play", args=[self.session.pin]))
        self.assertRedirects(response, reverse("join_lobby", args=[self.session.pin]))

    def test_session_play_view_get_in_progress(self):
        self.client.force_login(self.student)
        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = "in_progress"
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()
        response = self.client.get(reverse("session_play", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "session_play.html")
        self.assertEqual(response.context["question"].id, 1)  # из фикстуры

    def test_session_play_view_post_answer_correct(self):
        self.client.force_login(self.student)
        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = "in_progress"
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()
        # Правильный ответ для вопроса pk=1 из фикстуры – answer pk=1
        data = {"answer": "1", "timed_out": "0"}
        response = self.client.post(
            reverse("session_play", args=[self.session.pin]), data
        )
        self.assertRedirects(response, reverse("session_play", args=[self.session.pin]))
        # После ответа у единственного участника флаг сбрасывается (новый раунд),
        # но GameAnswer должна создаться и начислить баллы
        game_answer = GameAnswer.objects.filter(participant=participant).first()
        self.assertIsNotNone(game_answer)
        self.assertTrue(game_answer.is_correct)
        self.assertGreater(game_answer.points, 0)

    # --- quiz_sessions_list_view (для учителя) ---
    def test_quiz_sessions_list_view(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("quiz_sessions_list", args=[self.quiz.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz_sessions_list.html")
        self.assertIn("sessions", response.context)

    # --- session_results_teacher_view (детальные результаты) ---
    def test_session_results_teacher_view(self):
        self.client.force_login(self.teacher)
        participant = GameParticipant.objects.create(
            session=self.session, user=self.student, score=4
        )
        question = self.quiz.questions.first()
        GameAnswer.objects.create(
            session=self.session,
            participant=participant,
            question=question,
            is_correct=True,
            points=4,
        )
        response = self.client.get(
            reverse("session_results_teacher", args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "session_results_teacher.html")
        self.assertIn("rows", response.context)
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0]["user"], self.student)


class BugConditionExplorationTest(TestCase):
    """Тесты исследования баг-условий: очистка осиротевших сессий и переподключение игрока.

    **Проверяет: Требования 1.1, 1.2, 1.3**

    Эти тесты кодируют ОЖИДАЕМОЕ (правильное) поведение. Они спроектированы так,
    чтобы ПАДАТЬ на неисправленном коде, доказывая наличие багов.
    После применения исправления тесты должны проходить.
    """

    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.get(pk=2)
        self.student = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)  # active quiz

    def test_create_lobby_deletes_existing_waiting_session(self):
        """Случай A: Хост с существующей WAITING сессией создаёт новое лобби.

        Баг-условие (Треб. 1.2): create_lobby_view НЕ удаляет осиротевшие
        WAITING сессии при создании нового лобби для того же хоста.

        Ожидаемое поведение: старая WAITING сессия должна быть удалена.
        """
        # Create an existing WAITING session for the host
        old_session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="111111",
            status=GameSession.WAITING,
            is_locked=False,
        )
        old_session_id = old_session.id

        # Host creates a new lobby for the same quiz
        self.client.force_login(self.teacher)
        self.client.get(reverse("create_lobby", args=[self.quiz.id]))

        # Assert: the old WAITING session should no longer exist
        self.assertFalse(
            GameSession.objects.filter(id=old_session_id).exists(),
            "Bug confirmed: Old WAITING session was NOT deleted when host "
            "created a new lobby. create_lobby_view does not clean up orphans.",
        )

    def test_join_lobby_redirects_existing_participant_to_session_play(self):
        """Случай B: Существующий GameParticipant пытается войти в IN_PROGRESS сессию.

        Баг-условие (Треб. 1.3): join_lobby_view возвращает 200 с шаблоном ошибки
        вместо редиректа существующего участника на session_play.

        Ожидаемое поведение: должен быть редирект (302) на URL session_play.
        """
        # Create an IN_PROGRESS session
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="222222",
            status=GameSession.IN_PROGRESS,
            is_locked=False,
            current_question=0,
            current_question_started_at=timezone.now(),
        )

        # Create a GameParticipant for the student in this session
        GameParticipant.objects.create(session=session, user=self.student)

        # Student (existing participant) tries to join via PIN
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[session.pin]))

        # Assert: should be a redirect (302) to session_play
        self.assertEqual(
            response.status_code,
            302,
            "Bug confirmed: join_lobby_view returns 200 with error template "
            "instead of 302 redirect for existing participant in IN_PROGRESS session.",
        )
        self.assertIn(
            reverse("session_play", args=[session.pin]),
            response.url,
            "Bug confirmed: Redirect target is not session_play URL.",
        )

    def test_create_lobby_deletes_all_orphaned_waiting_sessions(self):
        """Случай C: Хост с несколькими WAITING сессиями создаёт новое лобби.

        Баг-условие (Треб. 1.2): create_lobby_view НЕ удаляет осиротевшие
        WAITING сессии, оставляя несколько «сирот» в базе данных.

        Ожидаемое поведение: все старые WAITING сессии должны быть удалены,
        и должна остаться только новая.
        """
        # Create multiple WAITING sessions for the host
        session1 = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="333333",
            status=GameSession.WAITING,
            is_locked=False,
        )
        session2 = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="444444",
            status=GameSession.WAITING,
            is_locked=False,
        )
        old_session_ids = [session1.id, session2.id]

        # Host creates a new lobby
        self.client.force_login(self.teacher)
        self.client.get(reverse("create_lobby", args=[self.quiz.id]))

        # Assert: all old WAITING sessions should be deleted
        remaining_old = GameSession.objects.filter(id__in=old_session_ids).count()
        self.assertEqual(
            remaining_old,
            0,
            "Bug confirmed: Old WAITING sessions were NOT deleted when host "
            "created a new lobby. Multiple orphans remain in the database.",
        )

        # Assert: only one WAITING session should exist for this host (the new one)
        waiting_sessions = GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING
        )
        self.assertEqual(
            waiting_sessions.count(),
            1,
            "Bug confirmed: Expected exactly 1 WAITING session after creating "
            "new lobby, but found multiple (orphans not cleaned up).",
        )
