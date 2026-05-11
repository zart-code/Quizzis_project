from django.test import TestCase
from django.contrib.auth.models import User
from main.models import (
    Profile,
    Quiz,
    Question,
    Answer,
    GameSession,
    GameParticipant,
    Category,
    QuizRevision,
    RevisionQuestion,
    RevisionAnswer,
    QuizResult,
    Achievement,
    UserAchievement,
    generate_pin,
)


class TestProfile(TestCase):
    fixtures = ["db.json"]

    def test_profile_creation_signal_for_new_user(self):
        user = User.objects.create(username="newuser")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.role, Profile.STUDENT)

    def test_admin_profile_auto_created_as_admin(self):
        admin = User.objects.create(username="admin")
        self.assertEqual(admin.profile.role, Profile.ADMIN)
        self.assertTrue(admin.profile.is_admin)

    def test_save_signal_corrects_role_for_admin_username(self):
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
    fixtures = ["db.json"]

    def test_total_questions_no_revision(self):
        quiz = Quiz.objects.get(pk=1)
        self.assertEqual(quiz.total_questions(), 1)

    def test_total_questions_with_revision(self):
        quiz = Quiz.objects.get(pk=1)
        rev = QuizRevision.objects.create(
            quiz=quiz, version=1, title="v1", question_count=3, max_score=12
        )
        quiz.current_revision = rev
        quiz.save()
        self.assertEqual(quiz.total_questions(), 3)

    def test_total_max_score_no_revision(self):
        quiz = Quiz.objects.get(pk=1)
        # question type 'multiple' coefficient=1 -> 4*1=4
        self.assertEqual(quiz.total_max_score(), 4)

    def test_total_max_score_with_revision(self):
        quiz = Quiz.objects.get(pk=1)
        rev = QuizRevision.objects.create(
            quiz=quiz, version=1, title="v1", max_score=20
        )
        quiz.current_revision = rev
        quiz.save()
        self.assertEqual(quiz.total_max_score(), 20)

    def test_str_method(self):
        quiz = Quiz.objects.get(pk=1)
        self.assertEqual(str(quiz), quiz.title)


class TestGameSession(TestCase):
    fixtures = ["db.json"]

    def test_pin_generated_on_creation(self):
        session = GameSession.objects.create(quiz_id=1, host_id=1)
        self.assertIsNotNone(session.pin)
        self.assertEqual(len(session.pin), 6)
        self.assertTrue(session.pin.isdigit())

    def test_default_status_is_waiting(self):
        session = GameSession.objects.create(quiz_id=1, host_id=1)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_str_contains_pin(self):
        session = GameSession.objects.get(pk=1)
        self.assertIn(session.pin, str(session))


class TestGameParticipant(TestCase):
    fixtures = ["db.json"]

    def test_default_values(self):
        session = GameSession.objects.get(pk=1)
        participant = GameParticipant.objects.create(session=session, user_id=1)
        self.assertEqual(participant.score, 0)
        self.assertFalse(participant.is_answered)
        self.assertIsNotNone(participant.joined_at)


class TestAnswer(TestCase):
    fixtures = ["db.json"]

    def test_answer_correctness_flag(self):
        correct = Answer.objects.get(pk=1)
        wrong = Answer.objects.get(pk=2)
        self.assertTrue(correct.is_correct)
        self.assertFalse(wrong.is_correct)


class TestQuizRevision(TestCase):
    fixtures = ["db.json"]

    def test_creation_and_ordering(self):
        quiz = Quiz.objects.get(pk=1)
        rev1 = QuizRevision.objects.create(quiz=quiz, version=1, title="v1")
        rev2 = QuizRevision.objects.create(quiz=quiz, version=2, title="v2")
        revisions = quiz.revisions.order_by("-version")
        self.assertEqual(list(revisions), [rev2, rev1])


class TestQuizResult(TestCase):
    def test_str_method_returns_score(self):
        result = QuizResult(user_id=1, quiz_id=1, score=10)
        self.assertEqual(str(result), "10")
