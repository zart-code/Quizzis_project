"""Тесты для моделей приложения main с использованием фикстуры db.json."""

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from main.models import (
    Answer,
    Category,
    GameAnswer,
    GameParticipant,
    GameSession,
    Question,
    Quiz,
    QuizResult,
    generate_pin,
)


class GeneratePinTest(TestCase):
    """Тесты генератора PIN-кода."""

    def test_pin_length_and_digits(self):
        pin = generate_pin()
        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isdigit())

    def test_pin_uniqueness_probabilistic(self):
        pins = [generate_pin() for _ in range(1000)]
        self.assertEqual(len(pins), len(set(pins)))


class CategoryModelTest(TestCase):
    """Тесты модели Category (данных в фикстуре нет, создаём сами)."""

    fixtures = ["db.json"]

    def test_str_method(self):
        category = Category.objects.create(
            name="Science", description="Natural sciences"
        )
        self.assertEqual(str(category), "Science")

    def test_unique_name_constraint(self):
        Category.objects.create(name="Math")
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Math")

    def test_ordering(self):
        Category.objects.create(name="Zoo")
        Category.objects.create(name="Alpha")
        categories = list(Category.objects.all())
        # ordering = ['name']
        self.assertEqual(
            [c.name for c in categories], ["Alpha", "Math", "Science", "Zoo"]
        )


class QuizModelTest(TestCase):
    """Тесты модели Quiz с использованием данных из фикстуры."""

    fixtures = ["db.json"]

    def setUp(self):
        self.quiz = Quiz.objects.get(pk=1)
        self.user = User.objects.get(pk=2)

    def test_str_method(self):
        self.assertEqual(str(self.quiz), "dsadda")

    def test_total_questions(self):
        self.assertEqual(self.quiz.total_questions(), 1)
        Question.objects.create(quiz=self.quiz, text="New question")
        self.assertEqual(self.quiz.total_questions(), 2)

    def test_default_is_published(self):
        self.assertFalse(self.quiz.is_published)

    def test_time_limit_nullable(self):
        self.assertIsNone(self.quiz.time_limit)

    def test_cascade_delete_creator(self):
        creator_id = self.user.id
        self.user.delete()
        self.assertEqual(Quiz.objects.filter(creator_id=creator_id).count(), 0)

    def test_category_on_delete_set_null(self):
        category = Category.objects.create(name="Temp")
        self.quiz.category = category
        self.quiz.save()
        category.delete()
        self.quiz.refresh_from_db()
        self.assertIsNone(self.quiz.category)


class QuestionModelTest(TestCase):
    """Тесты модели Question с использованием фикстуры."""

    fixtures = ["db.json"]

    def setUp(self):
        self.question = Question.objects.get(pk=1)
        self.quiz = self.question.quiz

    def test_str_method(self):
        self.assertEqual(str(self.question), "dasda")

    def test_question_type_from_fixture(self):
        self.assertEqual(self.question.question_type, Question.MULTIPLE)

    def test_default_time_limit(self):
        q = Question.objects.create(quiz=self.quiz, text="No time")
        self.assertEqual(q.time_limit, 30)

    def test_ordering(self):
        Question.objects.create(quiz=self.quiz, text="Order 1", order=10)
        Question.objects.create(quiz=self.quiz, text="Order 2", order=5)
        questions = list(Question.objects.filter(quiz=self.quiz))
        # Существующий вопрос имеет order=1
        self.assertEqual([q.order for q in questions], [1, 5, 10])

    def test_correct_number_for_numeric_question(self):
        numeric_q = Question.objects.create(
            quiz=self.quiz,
            text="Enter number",
            question_type=Question.NUMBER,
            correct_number=42.0,
        )
        self.assertEqual(numeric_q.correct_number, 42.0)

    def test_cascade_delete_quiz(self):
        quiz_id = self.quiz.id
        self.quiz.delete()
        self.assertEqual(Question.objects.filter(quiz_id=quiz_id).count(), 0)


class AnswerModelTest(TestCase):
    """Тесты модели Answer с использованием фикстуры."""

    fixtures = ["db.json"]

    def setUp(self):
        self.answer_correct = Answer.objects.get(pk=1)
        self.answer_wrong = Answer.objects.get(pk=2)
        self.question = self.answer_correct.question

    def test_str_method(self):
        self.assertEqual(str(self.answer_correct), "sdasda")
        self.assertEqual(str(self.answer_wrong), "zxczc")

    def test_is_correct_values(self):
        self.assertTrue(self.answer_correct.is_correct)
        self.assertFalse(self.answer_wrong.is_correct)

    def test_cascade_delete_question(self):
        question_id = self.question.id
        self.question.delete()
        self.assertEqual(Answer.objects.filter(question_id=question_id).count(), 0)


class QuizResultModelTest(TestCase):
    """Тесты модели QuizResult (данных в фикстуре нет, создаём сами)."""

    fixtures = ["db.json"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)

    def test_str_method(self):
        result = QuizResult.objects.create(
            user=self.user,
            quiz=self.quiz,
            score=5,
            max_score=10,
            score_percent=50.0,
            completed=False,
            order=1,
        )
        self.assertEqual(str(result), "5")

    def test_auto_fields(self):
        result = QuizResult.objects.create(user=self.user, quiz=self.quiz)
        self.assertIsNotNone(result.started_at)
        self.assertIsNone(result.completed_at)

    def test_ordering(self):
        QuizResult.objects.create(user=self.user, quiz=self.quiz, order=2)
        QuizResult.objects.create(user=self.user, quiz=self.quiz, order=1)
        results = list(QuizResult.objects.all())
        self.assertEqual([r.order for r in results], [1, 2])


class GameSessionModelTest(TestCase):
    """Тесты модели GameSession с использованием фикстуры."""

    fixtures = ["db.json"]

    def setUp(self):
        self.session = GameSession.objects.get(pk=1)
        self.quiz = self.session.quiz
        self.host = self.session.host

    def test_str_method(self):
        self.assertEqual(str(self.session), f"{self.quiz} [933327]")

    def test_pin_generation(self):
        new_session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertEqual(len(new_session.pin), 6)
        self.assertTrue(new_session.pin.isdigit())

    def test_pin_unique(self):
        with self.assertRaises(IntegrityError):
            GameSession.objects.create(
                quiz=self.quiz, host=self.host, pin=self.session.pin
            )

    def test_default_status_and_locked(self):
        new_session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertEqual(new_session.status, GameSession.WAITING)
        self.assertFalse(new_session.is_locked)
        self.assertEqual(new_session.current_question, 0)

    def test_ordering(self):
        s1 = GameSession.objects.create(quiz=self.quiz, host=self.host)
        s2 = GameSession.objects.create(quiz=self.quiz, host=self.host)
        sessions = list(GameSession.objects.all())
        # ordering = ['-created_at'] — новые первыми
        self.assertEqual(sessions[0], s2)
        self.assertEqual(sessions[1], s1)
        self.assertEqual(sessions[2], self.session)


class GameParticipantModelTest(TestCase):
    """Тесты модели GameParticipant."""

    fixtures = ["db.json"]

    def setUp(self):
        self.session = GameSession.objects.get(pk=1)
        self.user = User.objects.get(pk=1)

    def test_unique_together_session_user(self):
        GameParticipant.objects.create(session=self.session, user=self.user)
        with self.assertRaises(IntegrityError):
            GameParticipant.objects.create(session=self.session, user=self.user)

    def test_default_score_and_is_answered(self):
        part = GameParticipant.objects.create(session=self.session, user=self.user)
        self.assertEqual(part.score, 0)
        self.assertFalse(part.is_answered)

    def test_ordering_by_score_desc(self):
        p1 = GameParticipant.objects.create(
            session=self.session, user=self.user, score=10
        )
        user2 = User.objects.get(pk=2)
        p2 = GameParticipant.objects.create(session=self.session, user=user2, score=20)
        participants = list(GameParticipant.objects.all())
        self.assertEqual(participants, [p2, p1])

    def test_str_method(self):
        part = GameParticipant.objects.create(session=self.session, user=self.user)
        self.assertIn("присоединился", str(part))


class GameAnswerModelTest(TestCase):
    """Тесты модели GameAnswer."""

    fixtures = ["db.json"]

    def setUp(self):
        self.session = GameSession.objects.get(pk=1)
        self.user = User.objects.get(pk=1)
        self.participant = GameParticipant.objects.create(
            session=self.session, user=self.user
        )
        self.question = Question.objects.get(pk=1)
        self.answer = Answer.objects.get(pk=1)

    def test_unique_together_participant_question(self):
        GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        with self.assertRaises(IntegrityError):
            GameAnswer.objects.create(
                session=self.session,
                participant=self.participant,
                question=self.question,
                answer=self.answer,
            )

    def test_is_correct_default(self):
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
        )
        self.assertFalse(ans.is_correct)

    def test_answered_at_nullable(self):
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        self.assertIsNone(ans.answered_at)

    def test_str_method(self):
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        self.assertIn(str(self.answer), str(ans))
