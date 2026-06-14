"""Тесты для моделей приложения main"""

# pylint: disable=no-member

from django.test import TestCase
from apps.quiz.models import Quiz, QuizRevision, QuizResult, Answer


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
