"""Тесты для views_profile.py"""

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from main.models import Profile, QuizResult, Achievement, UserAchievement, Quiz


class ProfileViewsTest(TestCase):
    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.get(pk=1)
        self.user2 = User.objects.get(pk=2)
        self.quiz = Quiz.objects.get(pk=1)

        self.profile1 = Profile.objects.get(user=self.user1)
        self.profile2 = Profile.objects.get(user=self.user2)

        QuizResult.objects.get_or_create(
            user=self.user1,
            quiz=self.quiz,
            defaults={
                "score": 5,
                "max_score": 10,
                "score_percent": 50.0,
                "completed": True,
            },
        )
        QuizResult.objects.get_or_create(
            user=self.user2,
            quiz=self.quiz,
            defaults={
                "score": 9,
                "max_score": 10,
                "score_percent": 90.0,
                "completed": True,
            },
        )

    def assertLoginRedirect(self, response, expected_url):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(expected_url))

    # ------ profile_view ------
    def test_profile_view_own_authenticated(self):
        self.client.force_login(self.user1)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], self.user1)
        self.assertFalse(response.context["is_admin_view"])
        self.assertIn("achievements", response.context)
        self.assertIn("recent_quiz_history", response.context)

    def test_profile_view_other_as_admin(self):
        self.client.force_login(self.user2)
        response = self.client.get(
            reverse("admin_user_profile", kwargs={"user_id": self.user1.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], self.user1)
        self.assertTrue(response.context["is_admin_view"])

    def test_profile_view_other_as_non_admin(self):
        self.client.force_login(self.user1)
        response = self.client.get(
            reverse("admin_user_profile", kwargs={"user_id": self.user2.id})
        )
        self.assertRedirects(response, reverse("profile"))

    def test_profile_view_unauthenticated(self):
        response = self.client.get(reverse("profile"))
        self.assertLoginRedirect(response, reverse("login_page"))

    # ------ profile_history_view ------
    def test_profile_history_view_own(self):
        self.client.force_login(self.user1)
        response = self.client.get(reverse("profile_history"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], self.user1)
        self.assertFalse(response.context["is_admin_view"])

    def test_profile_history_view_other_as_admin(self):
        self.client.force_login(self.user2)
        response = self.client.get(
            reverse("admin_user_history", kwargs={"user_id": self.user1.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], self.user1)
        self.assertTrue(response.context["is_admin_view"])

    def test_profile_history_view_other_as_non_admin(self):
        self.client.force_login(self.user1)
        response = self.client.get(
            reverse("admin_user_history", kwargs={"user_id": self.user2.id})
        )
        self.assertRedirects(response, reverse("profile"))

    def test_profile_history_view_unauthenticated(self):
        response = self.client.get(reverse("profile_history"))
        self.assertLoginRedirect(response, reverse("login_page"))

    # ------ edit_profile_view ------
    def test_edit_profile_own_get(self):
        self.client.force_login(self.user1)
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edited_user"], self.user1)
        self.assertFalse(response.context["is_admin_edit"])

    def test_edit_profile_own_post_success(self):
        self.client.force_login(self.user1)
        data = {
            "username": "newusername",
            "email": "new@example.com",
            "password": "",
            "password_confirm": "",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("profile"))
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.username, "newusername")
        self.assertEqual(self.user1.email, "new@example.com")

    def test_edit_profile_own_post_change_password(self):
        self.client.force_login(self.user1)
        old_password = self.user1.password
        data = {
            "username": self.user1.username,
            "email": self.user1.email,
            "password": "newpassword123",
            "password_confirm": "newpassword123",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("profile"))
        self.user1.refresh_from_db()
        self.assertNotEqual(self.user1.password, old_password)
        self.assertTrue(
            self.client.login(username=self.user1.username, password="newpassword123")
        )

    def test_edit_profile_other_as_admin(self):
        self.client.force_login(self.user2)
        data = {
            "username": "edited_by_admin",
            "email": "admin_edit@example.com",
            "password": "adminpass123",
            "password_confirm": "adminpass123",
        }
        response = self.client.post(
            reverse("admin_edit_user", kwargs={"user_id": self.user1.id}), data
        )
        self.assertRedirects(
            response, reverse("admin_user_profile", kwargs={"user_id": self.user1.id})
        )
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.username, "edited_by_admin")
        self.assertEqual(self.user1.email, "admin_edit@example.com")
        self.assertTrue(self.user1.check_password("adminpass123"))

    def test_edit_profile_other_as_non_admin(self):
        self.client.force_login(self.user1)
        response = self.client.get(
            reverse("admin_edit_user", kwargs={"user_id": self.user2.id})
        )
        self.assertRedirects(response, reverse("profile"))

    def test_edit_profile_validation_duplicate_username(self):
        self.client.force_login(self.user1)
        data = {
            "username": self.user2.username,
            "email": self.user1.email,
            "password": "",
            "password_confirm": "",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("edit_profile"))
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("уже существует" in str(m) for m in messages))

    def test_edit_profile_validation_password_mismatch(self):
        self.client.force_login(self.user1)
        data = {
            "username": self.user1.username,
            "email": self.user1.email,
            "password": "pass123",
            "password_confirm": "pass321",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("edit_profile"))
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("не совпадают" in str(m) for m in messages))

    def test_edit_profile_validation_password_too_short(self):
        self.client.force_login(self.user1)
        data = {
            "username": self.user1.username,
            "email": self.user1.email,
            "password": "short",
            "password_confirm": "short",
        }
        response = self.client.post(reverse("edit_profile"), data)
        self.assertRedirects(response, reverse("edit_profile"))
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("не менее 8 символов" in str(m) for m in messages))

    def test_edit_profile_admin_edit_without_password(self):
        self.client.force_login(self.user2)
        data = {
            "username": "new_name",
            "email": "new@mail.com",
            "password": "",
            "password_confirm": "",
        }
        response = self.client.post(
            reverse("admin_edit_user", kwargs={"user_id": self.user1.id}), data
        )
        self.assertRedirects(
            response, reverse("admin_edit_user", kwargs={"user_id": self.user1.id})
        )
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("нужно указать пароль" in str(m) for m in messages))
