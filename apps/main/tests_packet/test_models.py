"""Тесты для моделей приложения main"""

# pylint: disable=no-member,missing-class-docstring,missing-function-docstring

from django.test import TestCase
from django.contrib.auth.models import User
from apps.quiz.models import Quiz, QuizRevision, QuizResult, Answer, Question


class TestAnswer(TestCase):
    """Тесты для модели Answer (вариант ответа на вопрос)."""

    def setUp(self):
        # Создаём минимально необходимое окружение
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.quiz = Quiz.objects.create(
            title="Sample Quiz", creator=self.user, status=Quiz.ACTIVE
        )
        self.question = Question.objects.create(quiz=self.quiz, text="Sample question")
        self.correct = Answer.objects.create(
            question=self.question, text="Correct", is_correct=True
        )
        self.wrong = Answer.objects.create(
            question=self.question, text="Wrong", is_correct=False
        )

    def test_answer_correctness_flag(self):
        """Флаг is_correct корректно отражает правильность варианта ответа."""
        self.assertTrue(self.correct.is_correct)
        self.assertFalse(self.wrong.is_correct)


class TestQuizRevision(TestCase):
    """Тесты для модели QuizRevision (версия квиза)."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.quiz = Quiz.objects.create(
            title="Test Quiz", creator=self.user, status=Quiz.ACTIVE
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