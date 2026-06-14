"""
Тесты для сервиса управления ревизиями квизов (quiz_revisions.py).
Тесты для сервиса подсчёта баллов (quiz_scoring.py).
"""

# pylint: disable=no-member

from apps.quiz.models import Question, Answer

from apps.main.services.quiz_scoring import SingleChoiceScoringStrategy, MultipleChoiceScoringStrategy, \
    NumberScoringStrategy, TextScoringStrategy, QuestionScoringFactory, build_submission_value, score_question
from apps.quiz.models import Quiz, QuizRevision
from django.http import QueryDict
from django.test import TestCase

from apps.main.services.quiz_revisions import get_current_revision, get_quiz_questions, create_revision_from_payloads, \
    build_revision_payload, collect_question_payloads_from_post, calculate_revision_totals, build_quiz_form_payload, \
    build_quiz_payload_for_edit


class MockRequest:
    """Заглушка для request, с атрибутом .POST как QueryDict."""

    def __init__(self, post_dict=None):
        """
        Инициализация заглушки запроса.

        Args:
            post_dict: Словарь с POST-данными. Если None, создаётся пустой QueryDict.
        """
        if post_dict is None:
            self.POST = QueryDict(mutable=True)
        else:
            # Преобразуем словарь в QueryDict
            qdict = QueryDict(mutable=True)
            for key, value in post_dict.items():
                if isinstance(value, list):
                    qdict.setlist(key, value)
                else:
                    qdict[key] = value
            self.POST = qdict


class TestRevisions(TestCase):
    """Набор тестов для функций управления ревизиями квизов."""

    fixtures = ["db.json"]

    def setUp(self):
        """Подготовка тестового окружения: получаем квиз из фикстур."""
        self.quiz = Quiz.objects.get(pk=1)

    def test_get_current_revision_none(self):
        """Проверка: у квиза без текущей ревизии возвращается None."""
        self.assertIsNone(get_current_revision(self.quiz))

    def test_get_current_revision_exists(self):
        """Проверка: при наличии текущей ревизии возвращается она."""
        rev = QuizRevision.objects.create(quiz=self.quiz, version=1, title="v1")
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(get_current_revision(self.quiz), rev)

    def test_get_quiz_questions_no_revision(self):
        """Если у квиза нет текущей ревизии, вопросы берутся напрямую из модели Question."""
        questions = get_quiz_questions(self.quiz)
        self.assertEqual(len(questions), 1)

    def test_get_quiz_questions_with_revision(self):
        """Если есть текущая ревизия, вопросы извлекаются из неё (RevisionQuestion)."""
        question_payload = {
            "text": "dasda",
            "question_type": "multiple",
            "time_limit": 30,
            "coefficient": 1,
            "order": 1,
            "correct_number": None,
            "answers": [
                {"text": "sdasda", "is_correct": True, "order": 1},
                {"text": "zxczc", "is_correct": False, "order": 2},
            ],
        }
        rev = create_revision_from_payloads(self.quiz, "Test Rev", [question_payload])
        self.quiz.current_revision = rev
        self.quiz.save()
        questions = get_quiz_questions(self.quiz)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].text, "dasda")

    def test_build_revision_payload(self):
        """Преобразование ревизии в словарь-payload для передачи в формы/API."""
        question_payload = {
            "text": "Revision question?",
            "question_type": "single",
            "time_limit": 30,
            "coefficient": 1,
            "order": 1,
            "correct_number": None,
            "answers": [
                {"text": "Right", "is_correct": True, "order": 1},
                {"text": "Wrong", "is_correct": False, "order": 2},
            ],
        }
        rev = create_revision_from_payloads(self.quiz, "Revision 1", [question_payload])
        payload = build_revision_payload(rev)
        self.assertEqual(payload["title"], "Revision 1")
        self.assertEqual(len(payload["questions"]), 1)
        q = payload["questions"][0]
        self.assertEqual(q["text"], "Revision question?")
        self.assertTrue(q["answers"][0]["is_correct"])

    def test_collect_question_payloads_single(self):
        """Сбор payload'ов вопросов из POST-данных для single-вопроса."""
        post_data = {
            "q0_text": "Q?",
            "q0_type": "single",
            "q0_time": "30",
            "q0_coefficient": "1",
            "q0_correct": "1",
            "q0_ans0": "Wrong",
            "q0_ans1": "Right",
        }
        request = MockRequest(post_data)
        payloads = collect_question_payloads_from_post(request)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["answers"][1]["is_correct"], True)
        self.assertEqual(payloads[0]["answers"][0]["is_correct"], False)

    def test_collect_question_payloads_multiple_correct(self):
        """Сбор payload'ов вопросов из POST-данных для multiple-вопроса с несколькими правильными ответами."""
        post_data = {
            "q0_text": "Q?",
            "q0_type": "multiple",
            "q0_correct": ["0", "2"],
            "q0_ans0": "A",
            "q0_ans1": "B",
            "q0_ans2": "C",
            "q0_ans3": "D",
        }
        request = MockRequest(post_data)
        payloads = collect_question_payloads_from_post(request)
        self.assertEqual(len(payloads), 1)
        self.assertTrue(payloads[0]["answers"][0]["is_correct"])
        self.assertTrue(payloads[0]["answers"][2]["is_correct"])
        self.assertFalse(payloads[0]["answers"][1]["is_correct"])

    def test_calculate_revision_totals(self):
        """Расчёт общего количества вопросов и максимального балла для ревизии."""
        payloads = [
            {"question_type": "single", "coefficient": 1},
            {"question_type": "text", "coefficient": 1},
        ]
        totals = calculate_revision_totals(payloads)
        self.assertEqual(totals["question_count"], 2)
        self.assertEqual(totals["max_score"], 4)  # text ignored

    def test_create_revision_from_payloads(self):
        """Создание новой ревизии из списка payload'ов вопросов."""
        payloads = [
            {
                "text": "Q",
                "question_type": "single",
                "time_limit": 30,
                "coefficient": 2,
                "order": 1,
                "correct_number": None,
                "answers": [
                    {"text": "A", "is_correct": True, "order": 1},
                    {"text": "B", "is_correct": False, "order": 2},
                ],
            }
        ]
        rev = create_revision_from_payloads(self.quiz, "New Rev", payloads)
        self.assertIsNotNone(rev)
        self.assertEqual(self.quiz.current_revision, rev)
        self.assertEqual(rev.question_count, 1)
        self.assertEqual(rev.max_score, 8)
        self.assertEqual(rev.title, "New Rev")

    def test_build_quiz_form_payload(self):
        """Построение полного payload'а для формы создания/редактирования квиза."""
        question_payloads = [
            {
                "text": "Q",
                "question_type": "single",
                "time_limit": 20,
                "coefficient": 1,
                "correct_number": None,
                "answers": [{"text": "A", "is_correct": True, "order": 1}],
            }
        ]
        payload = build_quiz_form_payload("Title", question_payloads)
        self.assertEqual(payload["title"], "Title")
        self.assertEqual(len(payload["questions"]), 1)

    def test_build_quiz_payload_for_edit_no_revision(self):
        """Построение payload'а для редактирования квиза, у которого нет ревизии."""
        payload = build_quiz_payload_for_edit(self.quiz)
        self.assertEqual(payload["title"], "dsadda")
        self.assertEqual(len(payload["questions"]), 1)


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
