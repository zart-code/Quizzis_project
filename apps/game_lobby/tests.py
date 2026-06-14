from apps.registration.models import Profile
from django.contrib.auth.models import User
from django.test import TestCase
from apps.quiz.models import Quiz, QuizRevision, GameSession, GameParticipant, Question


class TestProfile(TestCase):
    """Тесты для модели Profile и связанных сигналов."""

    def test_profile_creation_signal_for_new_user(self):
        user = User.objects.create(username="newuser")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.role, Profile.STUDENT)

    def test_admin_profile_auto_created_as_admin(self):
        admin = User.objects.create(username="admin")
        self.assertEqual(admin.profile.role, Profile.ADMIN)
        self.assertTrue(admin.profile.is_admin)

    def test_save_signal_corrects_role_for_admin_username(self):
        admin_user = User.objects.create(username="admin")
        # Убедимся, что роль изначально ADMIN
        self.assertEqual(admin_user.profile.role, Profile.ADMIN)

        # Меняем роль вручную
        admin_user.profile.role = Profile.STUDENT
        admin_user.profile.is_admin = False
        admin_user.profile.save()

        # Сохранение пользователя должно восстановить ADMIN
        admin_user.save()
        admin_user.refresh_from_db()
        self.assertEqual(admin_user.profile.role, Profile.ADMIN)
        self.assertTrue(admin_user.profile.is_admin)


class TestQuiz(TestCase):
    """Тесты для модели Quiz и её методов."""

    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="testpass")
        self.quiz = Quiz.objects.create(
            title="Test Quiz", creator=self.creator, status=Quiz.ACTIVE
        )
        # Один вопрос типа multiple с coefficient=1 → total_max_score = 4*1 = 4
        self.question = Question.objects.create(
            quiz=self.quiz,
            text="Sample question",
            question_type="multiple",
            coefficient=1,
            order=1,
        )

    def test_total_questions_no_revision(self):
        self.assertEqual(self.quiz.total_questions(), 1)

    def test_total_questions_with_revision(self):
        rev = QuizRevision.objects.create(
            quiz=self.quiz, version=1, title="v1", question_count=3, max_score=12
        )
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(self.quiz.total_questions(), 3)

    def test_total_max_score_no_revision(self):
        self.assertEqual(self.quiz.total_max_score(), 4)

    def test_total_max_score_with_revision(self):
        rev = QuizRevision.objects.create(
            quiz=self.quiz, version=1, title="v1", max_score=20
        )
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(self.quiz.total_max_score(), 20)

    def test_str_method(self):
        self.assertEqual(str(self.quiz), self.quiz.title)


class TestGameSession(TestCase):
    """Тесты для модели GameSession."""

    def setUp(self):
        self.host = User.objects.create_user(username="host", password="testpass")
        self.quiz = Quiz.objects.create(
            title="Session Quiz", creator=self.host, status=Quiz.ACTIVE
        )
        self.session = GameSession.objects.create(quiz=self.quiz, host=self.host)

    def test_pin_generated_on_creation(self):
        self.assertIsNotNone(self.session.pin)
        self.assertEqual(len(self.session.pin), 6)
        self.assertTrue(self.session.pin.isdigit())

    def test_default_status_is_waiting(self):
        self.assertEqual(self.session.status, GameSession.WAITING)

    def test_str_contains_pin(self):
        self.assertIn(self.session.pin, str(self.session))


class TestGameParticipant(TestCase):
    """Тесты для модели GameParticipant."""

    def setUp(self):
        self.user = User.objects.create_user(username="player", password="testpass")
        self.host = User.objects.create_user(username="host2", password="testpass")
        self.quiz = Quiz.objects.create(
            title="Participant Quiz", creator=self.host, status=Quiz.ACTIVE
        )
        self.session = GameSession.objects.create(quiz=self.quiz, host=self.host)

    def test_default_values(self):
        participant = GameParticipant.objects.create(
            session=self.session, user=self.user
        )
        self.assertEqual(participant.score, 0)
        self.assertFalse(participant.is_answered)
        self.assertIsNotNone(participant.joined_at)