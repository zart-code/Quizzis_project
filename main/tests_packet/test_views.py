from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class MainPageViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_main_page_anonymous(self):
        response = self.client.get(reverse("main_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main_page.html")

    def test_main_page_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("main_page"))
        self.assertEqual(response.status_code, 200)
        # Проверяем наличие ссылки на профиль (вместо прямого вывода имени)
        self.assertContains(response, "/profile/")


class LoginPageViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_login_page_get(self):
        response = self.client.get(reverse("login_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login_page.html")

    def test_login_page_post_success(self):
        response = self.client.post(
            reverse("login_page"),
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        self.assertRedirects(response, reverse("main_page"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_page_post_wrong_password(self):
        response = self.client.post(
            reverse("login_page"),
            {
                "username": "testuser",
                "password": "wrong",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверное имя пользователя или пароль")

    def test_login_page_post_nonexistent_user(self):
        response = self.client.post(
            reverse("login_page"),
            {
                "username": "noone",
                "password": "pass",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверное имя пользователя или пароль")


class RegisterPageViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_page_get(self):
        response = self.client.get(reverse("register_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "register.html")

    def test_register_page_post_success(self):
        response = self.client.post(
            reverse("register_page"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "role": "student",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        self.assertRedirects(response, reverse("main_page"))
        user = User.objects.filter(username="newuser").first()
        self.assertIsNotNone(user)
        self.assertTrue(user.check_password("strongpass123"))

    def test_register_page_post_passwords_mismatch(self):
        response = self.client.post(
            reverse("register_page"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "role": "student",
                "password1": "pass123",
                "password2": "pass321",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Ваша форма выдаёт сообщение на английском
        self.assertContains(response, "The two password fields didn’t match")

    def test_register_page_post_username_exists(self):
        User.objects.create_user(username="existing", password="pass")
        response = self.client.post(
            reverse("register_page"),
            {
                "username": "existing",
                "email": "new@example.com",
                "role": "student",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists")


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_logout_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("main_page"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_unauthenticated(self):
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("main_page"))
