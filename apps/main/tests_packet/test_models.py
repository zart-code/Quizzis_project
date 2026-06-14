"""Тесты для моделей приложения main"""

# pylint: disable=no-member

from django.test import TestCase
from django.contrib.auth.models import User
from apps.quiz.models import GameSession, GameParticipant
from apps.quiz_game.models import Quiz, QuizRevision, Answer, QuizResult
from apps.registration import Profile


class TestProfile(TestCase):
    """Тесты для модели Profile и связанных сигналов."""

    fixtures = ["db.json"]

    def test_profile_creation_signal_for_new_user(self):
        """
        Проверка: при создании нового пользователя автоматически создаётся профиль
        с ролью STUDENT (если имя не 'admin').
        """
        user = User.objects.create(username="newuser")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.role, Profile.STUDENT)

    def test_admin_profile_auto_created_as_admin(self):
        """
        Проверка: пользователь с именем 'admin' получает профиль с ролью ADMIN.
        """
        admin = User.objects.create(username="admin")
        self.assertEqual(admin.profile.role, Profile.ADMIN)
        self.assertTrue(admin.profile.is_admin)

    def test_save_signal_corrects_role_for_admin_username(self):
        """
        Проверка: при сохранении пользователя с именем 'admin' его профиль
        принудительно становится ADMIN (даже если была изменена роль).
        """
        admin_user = (
            User.objects.get(username="admin")
            if User.objects.filter(username="admin").exists()
            else User.objects.create(username="admin")
        )
        admin_user.profile.role = Profile.STUDENT
        admin_user.profile.is_admin = False
        admin_user.profile.save()
        admin_user.save()  # сигнал сработает при сохранении пользователя
        admin_user.refresh_from_db()
        self.assertEqual(admin_user.profile.role, Profile.ADMIN)
        self.assertTrue(admin_user.profile.is_admin)


class TestQuiz(TestCase):
    """Тесты для модели Quiz и её методов."""

    fixtures = ["db.json"]

    def test_total_questions_no_revision(self):
        """Метод total_questions() возвращает количество вопросов текущей ревизии."""
        quiz = Quiz.objects.get(pk=1)
        self.assertEqual(quiz.total_questions(), 1)

    def test_total_questions_with_revision(self):
        """Если у квиза есть текущая ревизия, total_questions() берёт question_count из неё."""
        quiz = Quiz.objects.get(pk=1)
        rev = QuizRevision.objects.create(
            quiz=quiz, version=1, title="v1", question_count=3, max_score=12
        )
        quiz.current_revision = rev
        quiz.save()
        self.assertEqual(quiz.total_questions(), 3)

    def test_total_max_score_no_revision(self):
        """Метод total_max_score() считает сумму коэффициентов вопросов, умноженных на 4."""
        quiz = Quiz.objects.get(pk=1)
        # question type 'multiple' coefficient=1 -> 4*1=4
        self.assertEqual(quiz.total_max_score(), 4)

    def test_total_max_score_with_revision(self):
        """Если есть текущая ревизия, total_max_score() берёт max_score из неё."""
        quiz = Quiz.objects.get(pk=1)
        rev = QuizRevision.objects.create(
            quiz=quiz, version=1, title="v1", max_score=20
        )
        quiz.current_revision = rev
        quiz.save()
        self.assertEqual(quiz.total_max_score(), 20)

    def test_str_method(self):
        """Строковое представление квиза — его заголовок."""
        quiz = Quiz.objects.get(pk=1)
        self.assertEqual(str(quiz), quiz.title)


class TestGameSession(TestCase):
    """Тесты для модели GameSession (игровая сессия)."""

    fixtures = ["db.json"]

    def test_pin_generated_on_creation(self):
        """При создании игровой сессии генерируется 6-значный PIN-код."""
        session = GameSession.objects.create(quiz_id=1, host_id=1)
        self.assertIsNotNone(session.pin)
        self.assertEqual(len(session.pin), 6)
        self.assertTrue(session.pin.isdigit())

    def test_default_status_is_waiting(self):
        """По умолчанию статус сессии — 'waiting' (ожидание игроков)."""
        session = GameSession.objects.create(quiz_id=1, host_id=1)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_str_contains_pin(self):
        """Строковое представление сессии содержит её PIN-код."""
        session = GameSession.objects.get(pk=1)
        self.assertIn(session.pin, str(session))


class TestGameParticipant(TestCase):
    """Тесты для модели GameParticipant (участник игровой сессии)."""

    fixtures = ["db.json"]

    def test_default_values(self):
        """Проверка значений по умолчанию: score=0, is_answered=False, joined_at заполняется."""
        session = GameSession.objects.get(pk=1)
        participant = GameParticipant.objects.create(session=session, user_id=1)
        self.assertEqual(participant.score, 0)
        self.assertFalse(participant.is_answered)
        self.assertIsNotNone(participant.joined_at)


class TestAnswer(TestCase):
    """Тесты для модели Answer (вариант ответа на вопрос)."""

    fixtures = ["db.json"]

    def test_answer_correctness_flag(self):
        """Флаг is_correct корректно отражает правильность варианта ответа."""
        correct = Answer.objects.get(pk=1)
        wrong = Answer.objects.get(pk=2)
        self.assertTrue(correct.is_correct)
        self.assertFalse(wrong.is_correct)


class TestQuizRevision(TestCase):
    """Тесты для модели QuizRevision (версия квиза)."""

    fixtures = ["db.json"]

    def test_creation_and_ordering(self):
        """Ревизии одного квиза упорядочиваются по убыванию номера версии."""
        quiz = Quiz.objects.get(pk=1)
        rev1 = QuizRevision.objects.create(quiz=quiz, version=1, title="v1")
        rev2 = QuizRevision.objects.create(quiz=quiz, version=2, title="v2")
        revisions = quiz.revisions.order_by("-version")
        self.assertEqual(list(revisions), [rev2, rev1])


class TestQuizResult(TestCase):
    """Тесты для модели QuizResult (результат прохождения квиза)."""

    def test_str_method_returns_score(self):
        """Строковое представление результата — это набранный балл."""
        result = QuizResult(user_id=1, quiz_id=1, score=10)
        self.assertEqual(str(result), "10")
