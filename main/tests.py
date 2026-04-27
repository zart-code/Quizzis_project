"""Тесты для моделей приложения main с использованием фикстуры db.json."""

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from main.models import (
    Answer,
    Category,
    GameAnswer,
    GameParticipant,
    GameSession,
    Question,
    Quiz,
    QuizResult,
    generate_pin,
)
from main.forms import CustomUserCreationForm, StyledAuthenticationForm


class GeneratePinTest(TestCase):
    """Тесты генератора PIN-кода."""

    def test_pin_length_and_digits(self):
        """Тестирование длины"""
        pin = generate_pin()
        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isdigit())

    def test_pin_uniqueness_probabilistic(self):
        """Тестирование на уникальность"""
        pins = [generate_pin() for _ in range(1000)]
        self.assertGreaterEqual(len(set(pins)), 990)


class CategoryModelTest(TestCase):
    """Тесты модели Category (используем данные из фикстуры)."""
    """Тесты модели Category."""

    fixtures = ["db.json"]

    def test_str_method(self):
        """Тестирование магического метода"""
        category = Category.objects.get(name="Science")  # из фикстуры
        self.assertEqual(str(category), "Science")

    def test_unique_name_constraint(self):
        """Тестирование на уникальность имени"""
        # Попытка создать дубликат существующего имени
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Math")

    def test_ordering(self):
        """Тестирование упорядоченности"""
        categories = list(Category.objects.all())
        self.assertEqual([c.name for c in categories], ["Alpha", "Zoo"])
        # ожидаемый порядок по name: Alpha, Math, Science, Zoo
        self.assertEqual(
            [c.name for c in categories], ["Alpha", "Math", "Science", "Zoo"]
        )


class QuizModelTest(TestCase):
    """Тесты модели Quiz."""

    fixtures = ["db.json"]

    def setUp(self):
        """Первичная настройка тестов"""
        self.quiz = Quiz.objects.get(pk=1)
        self.user = User.objects.get(pk=2)

    def test_str_method(self):
        """Тестирование магического метода"""
        self.assertEqual(str(self.quiz), "dsadda")

    def test_total_questions(self):
        """Тестирование работы функции total_questions"""
        self.assertEqual(self.quiz.total_questions(), 1)
        Question.objects.create(quiz=self.quiz, text="New question")
        self.assertEqual(self.quiz.total_questions(), 2)

    def test_time_limit_nullable(self):
        """Тестирование возможности обнуления времени"""
        self.assertIsNone(self.quiz.time_limit)

    def test_cascade_delete_creator(self):
        """Тестирование возможности удаления пользователя"""
        creator_id = self.user.id
        self.user.delete()
        self.assertEqual(Quiz.objects.filter(creator_id=creator_id).count(), 0)

    def test_category_on_delete_set_null(self):
        """Тестирование последствий удаления категорий"""
        category = Category.objects.create(name="Temp")
        self.quiz.category = category
        self.quiz.save()
        category.delete()
        self.quiz.refresh_from_db()
        self.assertIsNone(self.quiz.category)


class QuestionModelTest(TestCase):
    """Тесты модели Question."""

    fixtures = ["db.json"]

    def setUp(self):
        """Первичная настройка тестирования"""
        self.question = Question.objects.get(pk=1)
        self.quiz = self.question.quiz

    def test_str_method(self):
        """Тестирование магического метода"""
        self.assertEqual(str(self.question), "dasda")

    def test_question_type_from_fixture(self):
        """Тестирование фиксатуры"""
        self.assertEqual(self.question.question_type, Question.MULTIPLE)

    def test_default_time_limit(self):
        """Тестирование ограничения времени"""
        q = Question.objects.create(quiz=self.quiz, text="No time")
        self.assertEqual(q.time_limit, 30)

    def test_ordering(self):
        """Тестирование поля order"""
        Question.objects.create(quiz=self.quiz, text="Order 1", order=10)
        Question.objects.create(quiz=self.quiz, text="Order 2", order=5)
        questions = list(Question.objects.filter(quiz=self.quiz))
        self.assertEqual([q.order for q in questions], [1, 5, 10])

    def test_correct_number_for_numeric_question(self):
        """Корректность ответа на вопрос"""
        numeric_q = Question.objects.create(
            quiz=self.quiz,
            text="Enter number",
            question_type=Question.NUMBER,
            correct_number=42.0,
        )
        self.assertEqual(numeric_q.correct_number, 42.0)

    def test_cascade_delete_quiz(self):
        """Тестирование удаления квиза"""
        quiz_id = self.quiz.id
        self.quiz.delete()
        self.assertEqual(Question.objects.filter(quiz_id=quiz_id).count(), 0)


class GameAnswerModelTest(TestCase):
    """Тесты модели GameAnswer."""

    fixtures = ["db.json"]

    def setUp(self):
        """Настройка данных для проведения тестировавния"""
        self.session = GameSession.objects.get(pk=1)
        self.user = User.objects.get(pk=1)
        self.participant = GameParticipant.objects.get(session=self.session,
                                                       user=self.user)
        self.question = Question.objects.get(pk=1)
        self.answer = Answer.objects.get(pk=1)

        GameAnswer.objects.filter(participant=self.participant,
                                  question=self.question).delete()

    def test_unique_together_participant_question(self):
        """Тестирование уникальности вопроса участника"""
        GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        with self.assertRaises(IntegrityError):
            GameAnswer.objects.create(
                session=self.session,
                participant=self.participant,
                question=self.question,
                answer=self.answer,
            )

    def test_is_correct_default(self):
        """Стандартная проверка корректности"""
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
        )
        self.assertFalse(ans.is_correct)

    def test_answered_at_nullable(self):
        """Возможность обнуления ответа на тест"""
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        self.assertIsNone(ans.answered_at)

    def test_is_correct_values(self):
        self.assertTrue(self.answer_correct.is_correct)
        self.assertFalse(self.answer_wrong.is_correct)

    def test_cascade_delete_question(self):
        question_id = self.question.id
        self.question.delete()
        self.assertEqual(Answer.objects.filter(question_id=question_id).count(), 0)
    def test_str_method(self):
        """Тест метода"""
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        self.assertIn(str(self.answer), str(ans))


class QuizResultModelTest(TestCase):
    """Тесты модели QuizResult."""

    fixtures = ["db.json"]

    def setUp(self):
        """Первичная настройка тестов"""
        self.user = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)
        # Удаляем все результаты, чтобы не мешали
        QuizResult.objects.all().delete()

    def test_str_method(self):
        """Тестирование магического метода (зачем?)"""
        result = QuizResult.objects.create(
            user=self.user,
            quiz=self.quiz,
            score=5,
            max_score=10,
            score_percent=50.0,
            completed=False,
            order=1,
        )
        self.assertEqual(str(result), "5")

    def test_auto_fields(self):
        """Тестирование полей"""
        result = QuizResult.objects.create(user=self.user, quiz=self.quiz)
        self.assertIsNotNone(result.started_at)
        self.assertIsNone(result.completed_at)

    def test_ordering(self):
        """Тестирование order"""
        QuizResult.objects.create(user=self.user, quiz=self.quiz, order=2)
        QuizResult.objects.create(user=self.user, quiz=self.quiz, order=1)
        results = list(QuizResult.objects.all())
        self.assertEqual([r.order for r in results], [1, 2])


class GameSessionModelTest(TestCase):
    """Тесты модели GameSession."""

    fixtures = ["db.json"]

    def setUp(self):
        """Первичная настройка тестов"""
        self.session = GameSession.objects.get(pk=1)
        self.quiz = self.session.quiz
        self.host = self.session.host

    def test_str_method(self):
        """Тестирование магического метода"""
        self.assertEqual(str(self.session), f"{self.quiz} [933327]")

    def test_pin_generation(self):
        """Тестирование генератора pin"""
        new_session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertEqual(len(new_session.pin), 6)
        self.assertTrue(new_session.pin.isdigit())

    def test_pin_unique(self):
        """Тестирование уникальности пинов"""
        with self.assertRaises(IntegrityError):
            GameSession.objects.create(
                quiz=self.quiz, host=self.host, pin=self.session.pin
            )

    def test_default_status_and_locked(self):
        """Тестирование открытия и закрытия ишровой сессии"""
        new_session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertEqual(new_session.status, GameSession.WAITING)
        self.assertFalse(new_session.is_locked)
        self.assertEqual(new_session.current_question, 0)

    def test_ordering(self):
        """Тестирование order"""
        s1 = GameSession.objects.create(quiz=self.quiz, host=self.host)
        s2 = GameSession.objects.create(quiz=self.quiz, host=self.host)
        sessions = list(GameSession.objects.all())
        # ordering = ['-created_at'] — новые первыми
        self.assertEqual(sessions[0], s2)
        self.assertEqual(sessions[1], s1)
        self.assertEqual(sessions[2], self.session)


class GameParticipantModelTest(TestCase):
    """Тесты модели GameParticipant."""

    fixtures = ["db.json"]

    def setUp(self):
        """Первичная настройка"""
        self.session = GameSession.objects.get(pk=1)
        self.user = User.objects.get(pk=1)
        # Получаем существующего участника из фикстуры
        self.existing_participant = GameParticipant.objects.get(session=self.session,
                                                                user=self.user)

    def test_unique_together_session_user(self):
        """Уникальность игровых сессий и юзеров"""
        with self.assertRaises(IntegrityError):
            GameParticipant.objects.create(session=self.session, user=self.user)

    def test_default_score_and_is_answered(self):
        """Тестирование набирает балл по умолчанию и получает ответ"""
        user2 = User.objects.get(pk=2)
        part = GameParticipant.objects.create(session=self.session, user=user2)
        self.assertEqual(part.score, 0)
        self.assertFalse(part.is_answered)

    def test_ordering_by_score_desc(self):
        """Тестирование моих нервов"""
        user2 = User.objects.get(pk=2)
        p1 = GameParticipant.objects.create(session=self.session, user=user2, score=10)
        user3 = User.objects.create(username='user3', password='test')
        p2 = GameParticipant.objects.create(session=self.session, user=user3, score=20)
        participants = list(GameParticipant.objects.all())
        # Ожидаемый порядок: p2 (20), p1 (10), existing (0)
        self.assertEqual(participants, [p2, p1, self.existing_participant])

    def test_str_method(self):
        """Тестирование магического метода"""
        self.assertIn("присоединился", str(self.existing_participant))


class GameAnswerModelTest(TestCase):
    """Тесты модели GameAnswer."""

    fixtures = ["db.json"]

    def setUp(self):
        """Первичная настройка тестов"""
        self.session = GameSession.objects.get(pk=1)
        self.user = User.objects.get(pk=1)
        self.participant = GameParticipant.objects.create(
            session=self.session, user=self.user
        )
        self.question = Question.objects.get(pk=1)
        self.answer = Answer.objects.get(pk=1)
        # Очищаем предыдущие ответы, чтобы не мешали unique_together
        GameAnswer.objects.filter(participant=self.participant, question=self.question).delete()

    def test_unique_together_participant_question(self):
        """Тест на уникальность"""
        GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        with self.assertRaises(IntegrityError):
            GameAnswer.objects.create(
                session=self.session,
                participant=self.participant,
                question=self.question,
                answer=self.answer,
            )

    def test_is_correct_default(self):
        """Тест корректности начальных значений"""
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
        )
        self.assertFalse(ans.is_correct)

    def test_answered_at_nullable(self):
        """Тест обнуления ответа"""
        ans = GameAnswer.objects.create(
            session=self.session,
            participant=self.participant,
            question=self.question,
            answer=self.answer,
            is_correct=True,
        )
        self.assertIsNone(ans.answered_at)


class CustomUserCreationFormTest(TestCase):
    """Тесты формы регистрации."""

    def test_valid_data(self):
        form = CustomUserCreationForm(
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        self.assertTrue(form.is_valid())

    def test_password_mismatch(self):
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
        self.user = User.objects.create_user(
            username="loginuser", password="Secret12345"
        )

    def test_valid_credentials(self):
        form = StyledAuthenticationForm(
            data={"username": "loginuser", "password": "Secret12345"}
        )
        self.assertTrue(form.is_valid())

    def test_invalid_credentials(self):
        form = StyledAuthenticationForm(
            data={"username": "loginuser", "password": "wrong"}
        )
        self.assertFalse(form.is_valid())


class MainPageViewTest(TestCase):
    """Тесты главной страницы."""

    def test_main_page_status_code(self):
        response = self.client.get(reverse("main_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main_page.html")


class RegisterPageViewTest(TestCase):
    """Тесты страницы регистрации."""

    def test_get_register_page(self):
        response = self.client.get(reverse("register_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "register.html")

    def test_post_valid_registration(self):
        data = {
            "username": "freshuser",
            "email": "fresh@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        response = self.client.post(reverse("register_page"), data)
        self.assertRedirects(response, reverse("main_page"))
        self.assertTrue(User.objects.filter(username="freshuser").exists())

    def test_post_invalid_registration(self):
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
        self.user = User.objects.create_user(
            username="loginuser", password="Secret12345"
        )

    def test_get_login_page(self):
        response = self.client.get(reverse("login_page"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login_page.html")

    def test_post_valid_login(self):
        data = {"username": "loginuser", "password": "Secret12345"}
        response = self.client.post(reverse("login_page"), data)
        self.assertRedirects(response, reverse("main_page"))

    def test_post_invalid_login(self):
        data = {"username": "loginuser", "password": "wrong"}
        response = self.client.post(reverse("login_page"), data)
        self.assertEqual(response.status_code, 200)


class LogoutViewTest(TestCase):
    """Тесты выхода из системы."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="logoutuser", password="Secret12345"
        )
        self.client.login(username="logoutuser", password="Secret12345")

    def test_logout_redirects_to_main(self):
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("main_page"))


class QuizzesViewTest(TestCase):
    """Тесты страницы списка квизов."""

    fixtures = ["db.json"]

    def test_quizzes_view_default_sort(self):
        response = self.client.get(reverse("quizzes_view"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quizzes_view.html")
        self.assertEqual(response.context["current_sort"], "new")

    def test_quizzes_view_custom_sort(self):
        response = self.client.get(reverse("quizzes_view") + "?sort=popular")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_sort"], "popular")


class MyQuizzesViewTest(TestCase):
    """Тесты страницы «Мои квизы»."""

    def test_my_quizzes_status_code(self):
        response = self.client.get(reverse("my_quizzes"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_quizzes.html")
