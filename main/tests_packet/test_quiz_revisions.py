from django.test import TestCase
from django.http import QueryDict
from main.models import Quiz, QuizRevision
from main.services.quiz_revisions import (
    get_current_revision,
    get_revision_questions,
    get_quiz_questions,
    build_revision_payload,
    collect_question_payloads_from_post,
    calculate_revision_totals,
    create_revision_from_payloads,
    build_quiz_form_payload,
    build_quiz_payload_for_edit,
)


class MockRequest:
    """Заглушка для request, с атрибутом .POST как QueryDict."""

    def __init__(self, post_dict=None):
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
    fixtures = ["db.json"]

    def setUp(self):
        self.quiz = Quiz.objects.get(pk=1)

    def test_get_current_revision_none(self):
        self.assertIsNone(get_current_revision(self.quiz))

    def test_get_current_revision_exists(self):
        rev = QuizRevision.objects.create(quiz=self.quiz, version=1, title="v1")
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(get_current_revision(self.quiz), rev)

    def test_get_quiz_questions_no_revision(self):
        questions = get_quiz_questions(self.quiz)
        self.assertEqual(len(questions), 1)

    def test_get_quiz_questions_with_revision(self):
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
        payloads = [
            {"question_type": "single", "coefficient": 1},
            {"question_type": "text", "coefficient": 1},
        ]
        totals = calculate_revision_totals(payloads)
        self.assertEqual(totals["question_count"], 2)
        self.assertEqual(totals["max_score"], 4)  # text ignored

    def test_create_revision_from_payloads(self):
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
        payload = build_quiz_payload_for_edit(self.quiz)
        self.assertEqual(payload["title"], "dsadda")
        self.assertEqual(len(payload["questions"]), 1)
