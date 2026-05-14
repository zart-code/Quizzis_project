"""Тесты для представлений профиля (views_profile.py)."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class ProfileViewsTest(TestCase):
    """Набор тестов для всех представлений, связанных с профилем пользователя."""

    fixtures = ["db.json"]

    def setUp(self):
        """Настройка тестового окружения: создание клиента и пользователей разных ролей."""
        self.client = Client()
        self.student = User.objects.get(pk=1)
        self.teacher = User.objects.get(pk=2)
        self.admin = User.objects.create_superuser(
            username="admin", email="a@a.com", password="adminpass"
        )
        self.admin.profile.is_admin = True
        self.admin.profile.save()

    def test_profile_view_own(self):
        """Проверка: авторизованный пользователь видит свой собственный профиль."""
        self.client.force_login(self.student)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], self.student)

    def test_profile_view_other_as_admin(self):
        """Проверка: администратор может просматривать профиль другого пользователя."""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin_user_profile", args=[self.student.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_admin_view"])

    def test_profile_view_other_as_regular(self):
        """Проверка: обычный пользователь при попытке просмотра чужого профиля перенаправляется на свой."""
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("admin_user_profile", args=[self.teacher.id])
        )
        self.assertRedirects(response, reverse("profile"))

    def test_edit_profile_own_get(self):
        """GET-запрос на страницу редактирования своего профиля возвращает форму."""
        self.client.force_login(self.student)
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edited_user"], self.student)

    def test_edit_profile_own_post(self):
        """POST с изменёнными данными (без смены пароля) обновляет профиль."""
        self.client.force_login(self.student)
        data = {
            "username": "newname",
            "email": "new@mail.com",
            "password": "",
            "password_confirm": "",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("profile"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.username, "newname")

    def test_edit_profile_own_change_password(self):
        """POST с новым паролем корректно меняет пароль пользователя."""
        self.client.force_login(self.student)
        data = {
            "username": self.student.username,
            "email": self.student.email,
            "password": "newpass123",
            "password_confirm": "newpass123",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("profile"))
        self.assertTrue(
            self.client.login(username=self.student.username, password="newpass123")
        )

    def test_edit_profile_admin_edits_other(self):
        """Проверка: администратор может редактировать профиль другого пользователя."""
        self.client.force_login(self.admin)
        data = {
            "username": "edited_by_admin",
            "email": "edited@ex.com",
            "password": "adminpass123",
            "password_confirm": "adminpass123",
        }
        response = self.client.post(
            reverse("admin_edit_user", args=[self.student.id]), data
        )
        self.assertRedirects(
            response, reverse("admin_user_profile", args=[self.student.id])
        )
        self.student.refresh_from_db()
        self.assertEqual(self.student.username, "edited_by_admin")

    def test_profile_history_view_own(self):
        """Проверка: страница истории прохождений доступна собственному пользователю."""
        self.client.force_login(self.student)
        response = self.client.get(reverse("profile_history"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("quiz_history", response.context)

    def test_profile_history_view_other_as_admin(self):
        """Проверка: администратор может просматривать историю другого пользователя."""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin_user_history", args=[self.student.id])
        )
        self.assertEqual(response.status_code, 200)
