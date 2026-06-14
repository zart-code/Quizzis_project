"""Тесты для представлений админ-панели."""

# pylint: disable=no-member,missing-class-docstring,missing-function-docstring

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apps.quiz.models import Quiz


class AdminPanelViewsTest(TestCase):
    """Набор тестов для представлений админ-панели: просмотр панели, бан пользователя, снятие с публикации квиза."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="superadmin", email="admin@ex.com", password="adminpass"
        )
        self.admin.profile.is_admin = True
        self.admin.profile.save()

        # Явно создаём учителя, который раньше подгружался из фикстуры с pk=2
        self.teacher = User.objects.create_user(
            username="teacher", email="teacher@ex.com", password="teacherpass"
        )
        # Профиль для teacher будет создан автоматически (сигналом), если он есть в проекте.
        # Дополнительных действий не требуется.

        # Создаём активный квиз для тестов
        self.active_quiz = Quiz.objects.create(
            title="Active Quiz for Admin",
            creator=self.teacher,
            status=Quiz.ACTIVE,
        )

    def test_admin_panel_view(self):
        """GET-запрос к админ-панели возвращает страницу с формой."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel.html")

    def test_admin_ban_user_view(self):
        """POST-запрос банит пользователя и перенаправляет обратно в админ-панель."""
        self.client.force_login(self.admin)
        url = reverse("admin_ban_user", args=[self.teacher.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("admin_panel"))
        self.teacher.profile.refresh_from_db()
        self.assertTrue(self.teacher.profile.is_banned)

    def test_admin_unpublish_quiz_view(self):
        """POST-запрос переводит активный квиз в статус черновика."""
        self.client.force_login(self.admin)
        self.assertEqual(self.active_quiz.status, Quiz.ACTIVE)
        response = self.client.post(
            reverse("admin_unpublish_quiz", args=[self.active_quiz.id])
        )
        self.assertRedirects(response, reverse("admin_panel"))
        self.active_quiz.refresh_from_db()
        self.assertEqual(self.active_quiz.status, Quiz.DRAFT)