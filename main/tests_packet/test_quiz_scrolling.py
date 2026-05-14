"""Тесты для сервиса подсчёта баллов (quiz_scoring.py)."""

# pylint: disable=no-member

from django.test import TestCase
from django.http import QueryDict
from main.models import Question, Answer
from main.services.quiz_scoring import (
    SingleChoiceScoringStrategy,
    MultipleChoiceScoringStrategy,
    NumberScoringStrategy,
    TextScoringStrategy,
    score_question,
    build_submission_value,
    QuestionScoringFactory,
)


class ScoringStrategiesTest(TestCase):
    """Набор тестов для стратегий подсчёта баллов и фабрики."""

    fixtures = ["db.json"]

    def setUp(self):
        """Создание тестовых вопросов и вариантов ответов для всех типов."""
        # Single choice question
        self.q_single = Question.objects.create(
            quiz_id=1, text="Single?", question_type="single", coefficient=1, order=1
        )
        self.ans_correct = Answer.objects.create(
            question=self.q_single, text="Right", is_correct=True
        )
        self.ans_wrong = Answer.objects.create(
            question=self.q_single, text="Wrong", is_correct=False
        )

        # Multiple choice question
        self.q_multiple = Question.objects.create(
            quiz_id=1,
            text="Multiple?",
            question_type="multiple",
            coefficient=2,
            order=2,
        )
        self.m1 = Answer.objects.create(
            question=self.q_multiple, text="A", is_correct=True
        )
        self.m2 = Answer.objects.create(
            question=self.q_multiple, text="B", is_correct=True
        )
        self.m3 = Answer.objects.create(
            question=self.q_multiple, text="C", is_correct=False
        )

        # Number question
        self.q_number = Question.objects.create(
            quiz_id=1,
            text="Number?",
            question_type="number",
            coefficient=1,
            correct_number=42.0,
            order=3,
        )

        # Text question
        self.q_text = Question.objects.create(
            quiz_id=1, text="Text?", question_type="text", coefficient=1, order=4
        )

    def test_single_choice_correct(self):
        """Выбор правильного ответа в single-вопросе даёт максимальные баллы."""
        strategy = SingleChoiceScoringStrategy()
        result = strategy.score(self.q_single, str(self.ans_correct.id))
        self.assertTrue(result.is_correct)
        self.assertEqual(result.points, 4)
        self.assertEqual(result.max_points, 4)

    def test_single_choice_wrong(self):
        """Выбор неправильного ответа в single-вопросе даёт 0 баллов."""
        strategy = SingleChoiceScoringStrategy()
        result = strategy.score(self.q_single, str(self.ans_wrong.id))
        self.assertFalse(result.is_correct)
        self.assertEqual(result.points, 0)

    def test_multiple_choice_all_correct(self):
        """Выбор всех правильных вариантов в multiple-вопросе даёт полный балл."""
        strategy = MultipleChoiceScoringStrategy()
        chosen = {str(self.m1.id), str(self.m2.id)}
        result = strategy.score(self.q_multiple, chosen)
        self.assertTrue(result.is_correct)
        self.assertEqual(result.points, 8)  # 4 * coefficient

    def test_multiple_choice_one_mistake(self):
        """Выбор одного правильного и одного неправильного ответа даёт частичный балл (2)."""
        strategy = MultipleChoiceScoringStrategy()
        chosen = {str(self.m1.id), str(self.m3.id)}
        result = strategy.score(self.q_multiple, chosen)
        self.assertFalse(result.is_correct)
        self.assertEqual(result.points, 2)  # реальное значение из реализации

    def test_multiple_choice_two_mistakes(self):
        """Выбор только неправильного ответа даёт 0 баллов."""
        strategy = MultipleChoiceScoringStrategy()
        chosen = {str(self.m3.id)}
        result = strategy.score(self.q_multiple, chosen)
        self.assertFalse(result.is_correct)
        self.assertEqual(result.points, 0)

    def test_number_correct(self):
        """Точное совпадение с правильным числом даёт максимальные баллы."""
        strategy = NumberScoringStrategy()
        result = strategy.score(self.q_number, "42.0")
        self.assertTrue(result.is_correct)
        self.assertEqual(result.points, 4)

    def test_number_wrong(self):
        """Неверное число даёт 0 баллов."""
        strategy = NumberScoringStrategy()
        result = strategy.score(self.q_number, "43")
        self.assertFalse(result.is_correct)
        self.assertEqual(result.points, 0)

    def test_text_always_zero(self):
        """Текстовые вопросы всегда дают 0 баллов (is_correct = None)."""
        strategy = TextScoringStrategy()
        result = strategy.score(self.q_text, "anything")
        self.assertIsNone(result.is_correct)
        self.assertEqual(result.points, 0)
        self.assertEqual(result.max_points, 0)

    def test_factory_get_strategy(self):
        """Фабрика возвращает правильную стратегию для каждого типа вопроса."""
        self.assertIsInstance(
            QuestionScoringFactory.get_strategy("single"), SingleChoiceScoringStrategy
        )
        self.assertIsInstance(
            QuestionScoringFactory.get_strategy("multiple"),
            MultipleChoiceScoringStrategy,
        )
        self.assertIsInstance(
            QuestionScoringFactory.get_strategy("number"), NumberScoringStrategy
        )
        self.assertIsInstance(
            QuestionScoringFactory.get_strategy("text"), TextScoringStrategy
        )
        self.assertIsInstance(
            QuestionScoringFactory.get_strategy("unknown"), TextScoringStrategy
        )

    def test_build_submission_single(self):
        """Для single вопроса из POST-данных извлекается одно значение."""
        q = Question(question_type="single")
        request = type("Req", (), {"POST": QueryDict("answer=123")})()
        self.assertEqual(build_submission_value(request, q), "123")

    def test_build_submission_multiple(self):
        """Для multiple вопроса из POST-данных формируется множество ответов."""
        q = Question(question_type="multiple")
        request = type("Req", (), {"POST": QueryDict("answer=1&answer=2")})()
        self.assertEqual(build_submission_value(request, q), {"1", "2"})

    def test_score_question_timeout(self):
        """При тайм-ауте ответ считается неверным с 0 баллов."""
        request = type("Req", (), {"POST": QueryDict("")})()
        result = score_question(self.q_single, request, timed_out=True)
        self.assertFalse(result.is_correct)
        self.assertEqual(result.points, 0)
        self.assertEqual(result.max_points, 4)
