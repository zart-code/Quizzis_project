"""Тесты для представлений лобби (views_lobby.py)."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from main.models import Quiz, GameSession, GameParticipant

class LobbyViewsTest(TestCase):
    fixtures = ['db.json']

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.get(pk=2)
        self.student = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)               # активный
        self.session = GameSession.objects.create(
            quiz=self.quiz, host=self.teacher, pin='123456',
            status=GameSession.WAITING, is_locked=False
        )

    def test_create_lobby_view(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('create_lobby', args=[self.quiz.id]))
        self.assertRedirects(response, reverse('my_quizzes'), fetch_redirect_response=False)
        session = GameSession.objects.filter(quiz=self.quiz, host=self.teacher).last()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_lobby_view_get(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('lobby', args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['session'], self.session)

    def test_lobby_view_non_host(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('lobby', args=[self.session.pin]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_lock_view(self):
        self.client.force_login(self.teacher)
        self.assertFalse(self.session.is_locked)
        response = self.client.post(reverse('toggle_lock', args=[self.session.pin]))
        self.assertRedirects(response, reverse('lobby', args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_locked)

    def test_delete_session_view(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('delete_session', args=[self.session.pin]))
        self.assertRedirects(response, reverse('my_quizzes'), fetch_redirect_response=False)
        with self.assertRaises(GameSession.DoesNotExist):
            self.session.refresh_from_db()

    def test_start_game_view(self):
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(session=self.session, user=self.student)
        response = self.client.post(reverse('start_game', args=[self.session.pin]))
        self.assertRedirects(response, reverse('lobby', args=[self.session.pin]))
        self.session.refresh_from_db()
        # Исправлено: статус 'in_progress' вместо 'active'
        self.assertEqual(self.session.status, 'in_progress')