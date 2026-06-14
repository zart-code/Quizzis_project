"""Тесты для моделей приложения main"""

# pylint: disable=no-member

from django.test import TestCase
from django.contrib.auth.models import User
from apps.quiz.models import (
    GameSession,
    GameParticipant,
    Quiz,
    QuizRevision,
    Answer,
    QuizResult,
    Question,
)
from apps.registration.models import Profile


class TestProfile(TestCase):
    """Тесты для модели Profile и связанных сигналов."""

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
        # Создаём или получаем пользователя с именем "admin"
        admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"email": ""}
        )
        # Пытаемся изменить роль на STUDENT
        admin_user.profile.role = Profile.STUDENT
        admin_user.profile.is_admin = False
        admin_user.profile.save()
        admin_user.save()  # сигнал должен восстановить права
        admin_user.refresh_from_db()
        self.assertEqual(admin_user.profile.role, Profile.ADMIN)
        self.assertTrue(admin_user.profile.is_admin)


class TestQuiz(TestCase):
    """Тесты для модели Quiz и её методов."""

    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username="teacher", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Test Quiz", creator=cls.host, status=Quiz.ACTIVE
        )
        # Вопрос с коэффициентом 1 (multiple) для проверки max_score = 4
        cls.question = Question.objects.create(
            quiz=cls.quiz,
            text="Sample question",
            question_type="multiple",
            coefficient=1,
            order=1,
        )

    def test_total_questions_no_revision(self):
        """Метод total_questions() возвращает количество вопросов текущей ревизии."""
        self.assertEqual(self.quiz.total_questions(), 1)

    def test_total_questions_with_revision(self):
        """Если у квиза есть текущая ревизия, total_questions() берёт question_count из неё."""
        rev = QuizRevision.objects.create(
            quiz=self.quiz, version=1, title="v1", question_count=3, max_score=12
        )
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(self.quiz.total_questions(), 3)

    def test_total_max_score_no_revision(self):
        """Метод total_max_score() считает сумму коэффициентов вопросов, умноженных на 4."""
        # question type 'multiple' coefficient=1 -> 4*1=4
        self.assertEqual(self.quiz.total_max_score(), 4)

    def test_total_max_score_with_revision(self):
        """Если есть текущая ревизия, total_max_score() берёт max_score из неё."""
        rev = QuizRevision.objects.create(
            quiz=self.quiz, version=1, title="v1", max_score=20
        )
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(self.quiz.total_max_score(), 20)

    def test_str_method(self):
        """Строковое представление квиза — его заголовок."""
        self.assertEqual(str(self.quiz), "Test Quiz")


class TestGameSession(TestCase):
    """Тесты для модели GameSession (игровая сессия)."""

    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username="host_user", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Session Quiz", creator=cls.host, status=Quiz.ACTIVE
        )
        # Создаём базовую сессию для теста test_str_contains_pin
        cls.session = GameSession.objects.create(
            quiz=cls.quiz, host=cls.host, pin="123456", status=GameSession.WAITING
        )

    def test_pin_generated_on_creation(self):
        """При создании игровой сессии генерируется 6-значный PIN-код."""
        # Создаём новую сессию без указания pin, чтобы сработала авто-генерация
        session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertIsNotNone(session.pin)
        self.assertEqual(len(session.pin), 6)
        self.assertTrue(session.pin.isdigit())

    def test_default_status_is_waiting(self):
        """По умолчанию статус сессии — 'waiting' (ожидание игроков)."""
        session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_str_contains_pin(self):
        """Строковое представление сессии содержит её PIN-код."""
        self.assertIn(self.session.pin, str(self.session))


class TestGameParticipant(TestCase):
    """Тесты для модели GameParticipant (участник игровой сессии)."""

    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username="host", password="testpass")
        cls.player = User.objects.create_user(username="player", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Participant Quiz", creator=cls.host, status=Quiz.ACTIVE
        )
        cls.session = GameSession.objects.create(
            quiz=cls.quiz, host=cls.host, pin="654321", status=GameSession.WAITING
        )

    def test_default_values(self):
        """Проверка значений по умолчанию: score=0, is_answered=False, joined_at заполняется."""
        participant = GameParticipant.objects.create(
            session=self.session, user=self.player
        )
        self.assertEqual(participant.score, 0)
        self.assertFalse(participant.is_answered)
        self.assertIsNotNone(participant.joined_at)


class TestAnswer(TestCase):
    """Тесты для модели Answer (вариант ответа на вопрос)."""

    @classmethod
    def setUpTestData(cls):
        host = User.objects.create_user(username="quiz_author", password="testpass")
        quiz = Quiz.objects.create(
            title="Answer Quiz", creator=host, status=Quiz.ACTIVE
        )
        question = Question.objects.create(
            quiz=quiz, text="Q", question_type="single", coefficient=1, order=1
        )
        cls.correct_answer = Answer.objects.create(
            question=question, text="Right", is_correct=True
        )
        cls.wrong_answer = Answer.objects.create(
            question=question, text="Wrong", is_correct=False
        )

    def test_answer_correctness_flag(self):
        """Флаг is_correct корректно отражает правильность варианта ответа."""
        self.assertTrue(self.correct_answer.is_correct)
        self.assertFalse(self.wrong_answer.is_correct)


class TestQuizRevision(TestCase):
    """Тесты для модели QuizRevision (версия квиза)."""

    @classmethod
    def setUpTestData(cls):
        host = User.objects.create_user(username="revision_author", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Revision Quiz", creator=host, status=Quiz.ACTIVE
        )

    def test_creation_and_ordering(self):
        """Ревизии одного квиза упорядочиваются по убыванию номера версии."""
        rev1 = QuizRevision.objects.create(quiz=self.quiz, version=1, title="v1")
        rev2 = QuizRevision.objects.create(quiz=self.quiz, version=2, title="v2")
        revisions = self.quiz.revisions.order_by("-version")
        self.assertEqual(list(revisions), [rev2, rev1])


class TestQuizResult(TestCase):
    """Тесты для модели QuizResult (результат прохождения квиза)."""

    def test_str_method_returns_score(self):
        """Строковое представление результата — это набранный балл."""
        result = QuizResult(user_id=1, quiz_id=1, score=10)
        self.assertEqual(str(result), "10")