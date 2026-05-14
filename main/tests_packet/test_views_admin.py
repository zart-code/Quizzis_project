"""Тесты для представлений админ-панели."""

# pylint: disable=no-member,missing-class-docstring,missing-function-docstring

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from main.models import GameSession, Quiz, QuizResult, QuizRevision


class AdminPanelViewsTest(TestCase):
    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="superadmin", email="admin@ex.com", password="adminpass"
        )
        self.admin.profile.is_admin = True
        self.admin.profile.save()
        self.teacher = User.objects.get(pk=2)
        # Создаём активный квиз для тестов
        self.active_quiz = Quiz.objects.create(
            title="Active Quiz for Admin",
            creator=self.teacher,
            status=Quiz.ACTIVE,
        )

    def test_admin_panel_view(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel.html")

    def test_admin_ban_user_view(self):
        self.client.force_login(self.admin)
        url = reverse("admin_ban_user", args=[self.teacher.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("admin_panel"))
        self.teacher.profile.refresh_from_db()
        self.assertTrue(self.teacher.profile.is_banned)

    def test_admin_unpublish_quiz_view(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.active_quiz.status, Quiz.ACTIVE)
        response = self.client.post(
            reverse("admin_unpublish_quiz", args=[self.active_quiz.id])
        )
        self.assertRedirects(response, reverse("admin_panel"))
        self.active_quiz.refresh_from_db()
        self.assertEqual(self.active_quiz.status, Quiz.DRAFT)

    def test_admin_delete_quiz_view(self):
        self.client.force_login(self.admin)
        quiz_id = self.active_quiz.id
        url = reverse("admin_delete_quiz", args=[quiz_id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("admin_panel"))
        with self.assertRaises(Quiz.DoesNotExist):
            Quiz.objects.get(pk=quiz_id)

    def test_admin_delete_quiz_view_with_revision_history(self):
        self.client.force_login(self.admin)
        revision = QuizRevision.objects.create(
            quiz=self.active_quiz,
            version=1,
            title="Revision with history",
        )
        self.active_quiz.current_revision = revision
        self.active_quiz.save(update_fields=["current_revision"])
        GameSession.objects.create(
            quiz=self.active_quiz,
            host=self.teacher,
            revision=revision,
        )
        QuizResult.objects.create(
            user=self.teacher,
            quiz=self.active_quiz,
            revision=revision,
        )

        response = self.client.post(
            reverse("admin_delete_quiz", args=[self.active_quiz.id])
        )

        self.assertRedirects(response, reverse("admin_panel"))
        self.assertFalse(Quiz.objects.filter(pk=self.active_quiz.id).exists())
        self.assertFalse(QuizRevision.objects.filter(pk=revision.id).exists())
        session_exists = GameSession.objects.filter(revision=revision).exists()
        self.assertFalse(session_exists)
        self.assertFalse(QuizResult.objects.filter(revision=revision).exists())
