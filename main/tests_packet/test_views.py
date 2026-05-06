"""Тесты для файла views.py"""

import time
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from main.forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models import Quiz, Question


class CustomUserCreationFormTest(TestCase):
    """Тесты формы регистрации."""

    def test_valid_data(self):
        """Проверка валидных данных формы регистрации."""
        unique_name = f"newuser_{int(time.time())}"
        form = CustomUserCreationForm(
            data={
                "username": unique_name,
                "email": f"{unique_name}@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "role": "teacher",  # или 'student', но для my_quizzes нужен teacher
            }
        )
        if not form.is_valid():
            print("Form errors:", form.errors)
        self.assertTrue(form.is_valid())

    def test_password_mismatch(self):
        """Проверка несовпадения паролей."""
        form = CustomUserCreationForm(
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password1": "ComplexPass123!",
                "password2": "DifferentPass1!",
            }
        )
        self.assertFalse(form.is_valid())

    def test_existing_username(self):
        """Проверка валидации уже существующего имени пользователя."""
        User.objects.create_user(username="existing")
        form = CustomUserCreationForm(
            data={
                "username": "existing",
                "email": "e@e.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        self.assertFalse(form.is_valid())


class StyledAuthenticationFormTest(TestCase):
    """Тесты формы аутентификации."""

    def setUp(self):
        """Создание тестового пользователя."""
        self.user = User.objects.create_user(
            username="loginuser", password="Secret12345"
        )

    def test_valid_credentials(self):
        """Проверка валидных учётных данных."""
        form = StyledAuthenticationForm(
            data={"username": "loginuser", "password": "Secret12345"}
        )
        self.assertTrue(form.is_valid())

    def test_invalid_credentials(self):
        """Проверка неверных учётных данных."""
        form = StyledAuthenticationForm(
            data={"username": "loginuser", "password": "wrong"}
        )
        self.assertFalse(form.is_valid())


class MainPageViewTest(TestCase):
    """Тесты главной страницы."""

    def test_main_page_status_code(self):
        """Проверка статуса и шаблона главной страницы."""
        response = self.client.get(reverse("main_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main_page.html")


class RegisterPageViewTest(TestCase):
    """Тесты страницы регистрации."""

    def test_get_register_page(self):
        """Проверка GET-запроса на страницу регистрации."""
        response = self.client.get(reverse("register_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "register.html")

    def test_post_valid_registration(self):
        """Проверка успешной регистрации через POST."""
        unique = f"freshuser_{int(time.time())}"
        data = {
            "username": unique,
            "email": f"{unique}@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
            "role": "teacher",
        }
        response = self.client.post(reverse("register_page"), data)
        if response.status_code != 302 and "form" in response.context:
            print(response.context["form"].errors)
        self.assertRedirects(response, reverse("main_page"))
        self.assertTrue(User.objects.filter(username=unique).exists())

    def test_post_invalid_registration(self):
        """Проверка неудачной регистрации с некорректными данными."""
        data = {
            "username": "bad",
            "email": "bad@example.com",
            "password1": "Short1!",
            "password2": "Short1!",
        }
        response = self.client.post(reverse("register_page"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="bad").exists())


class LoginPageViewTest(TestCase):
    """Тесты страницы входа."""

    def setUp(self):
        """Создание тестового пользователя."""
        self.user = User.objects.create_user(
            username="loginuser", password="Secret12345"
        )

    def test_get_login_page(self):
        """Проверка GET-запроса на страницу входа."""
        response = self.client.get(reverse("login_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login_page.html")

    def test_post_valid_login(self):
        """Проверка успешного входа."""
        data = {"username": "loginuser", "password": "Secret12345"}
        response = self.client.post(reverse("login_page"), data)
        self.assertRedirects(response, reverse("main_page"))

    def test_post_invalid_login(self):
        """Проверка входа с неверным паролем."""
        data = {"username": "loginuser", "password": "wrong"}
        response = self.client.post(reverse("login_page"), data)
        self.assertEqual(response.status_code, 200)


class LogoutViewTest(TestCase):
    """Тесты выхода из системы."""

    def setUp(self):
        """Создание и авторизация тестового пользователя."""
        self.user = User.objects.create_user(
            username="logoutuser", password="Secret12345"
        )
        self.client.login(username="logoutuser", password="Secret12345")

    def test_logout_redirects_to_main(self):
        """Проверка редиректа после выхода."""
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("main_page"))


class QuizzesViewTest(TestCase):
    """Тесты страницы списка квизов."""

    fixtures = ["db.json"]

    def test_quizzes_view_default_sort(self):
        """Проверка сортировки по умолчанию (новые)."""
        response = self.client.get(reverse("quizzes_view"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quizzes_view.html")
        self.assertEqual(response.context["current_sort"], "new")

    def test_quizzes_view_custom_sort(self):
        """Проверка сортировки по популярности."""
        response = self.client.get(reverse("quizzes_view") + "?sort=popular")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_sort"], "popular")


class MyQuizzesViewTest(TestCase):
    """Тесты страницы 'Мои квизы'."""

    def setUp(self):
        """Создание суперпользователя, настройка профиля и создание тестового квиза."""
        # Создаём суперпользователя (все права)
        self.user = User.objects.create_superuser(
            username="testuser_my", password="testpass123", email="test@example.com"
        )
        # Получаем профиль и настраиваем его
        profile = self.user.profile
        profile.role = "teacher"  # попробуем teacher вместо admin
        profile.is_admin = True
        profile.save()

        # Создаём квиз
        self.quiz = Quiz.objects.create(
            title="Test Quiz", creator=self.user, status=Quiz.ACTIVE, description="Test"
        )
        Question.objects.create(quiz=self.quiz, text="Sample question", order=1)
        self.client.force_login(self.user)

    def test_my_quizzes_status_code(self):
        """Проверка статуса и шаблона страницы 'Мои квизы'."""
        response = self.client.get(reverse("my_quizzes"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_quizzes.html")
