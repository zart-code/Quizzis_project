"""Тесты для представлений админ-панели (admin_panel, ban, unpublish, delete)."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from main.models import Quiz


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
        # Создаём активный квиз специально для тестов
        self.active_quiz = Quiz.objects.create(
            title="Active Quiz for Admin", creator=self.teacher, status=Quiz.ACTIVE
        )

    def test_admin_panel_view(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel.html")

    def test_admin_ban_user_view(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_ban_user", args=[self.teacher.id]))
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
        response = self.client.post(reverse("admin_delete_quiz", args=[quiz_id]))
        self.assertRedirects(response, reverse("admin_panel"))
        with self.assertRaises(Quiz.DoesNotExist):
            Quiz.objects.get(pk=quiz_id)
