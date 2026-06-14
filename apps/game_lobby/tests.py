from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.quiz.models import Quiz, Question, Answer, GameSession, GameParticipant, GameAnswer, QuizRevision, QuizResult
from apps.registration.models import Profile


# Create your tests here.
class LobbyViewsTest(TestCase):
    """Набор тестов для всех представлений, связанных с игровым лобби."""

    @classmethod
    def setUpTestData(cls):
        """Создаёт базовых пользователей и активный квиз."""
        cls.teacher = User.objects.create_user(
            username='teacher', password='testpass'
        )
        cls.student = User.objects.create_user(
            username='student', password='testpass'
        )
        cls.quiz = Quiz.objects.create(
            title='Test Quiz',
            creator=cls.teacher,
            status=Quiz.ACTIVE,
        )
        # Создаём вопрос с ответами для тестов, которым нужен вопрос
        cls.question = Question.objects.create(
            quiz=cls.quiz,
            text='Test question',
            question_type='single',
            coefficient=1,
            order=1,
        )
        cls.correct_answer = Answer.objects.create(
            question=cls.question, text='Correct', is_correct=True
        )
        cls.wrong_answer = Answer.objects.create(
            question=cls.question, text='Wrong', is_correct=False
        )

    def setUp(self):
        """Создаёт клиент и базовую сессию перед каждым тестом."""
        self.client = Client()
        # Базовая WAITING-сессия для большинства тестов
        self.session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='123456',
            status=GameSession.WAITING,
            is_locked=False,
        )

    # --- create_lobby_view ---
    def test_create_lobby_view(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("create_lobby", args=[self.quiz.id]))
        # Ожидаем редирект на lobby с PIN новой сессии
        new_session = GameSession.objects.filter(host=self.teacher, status=GameSession.WAITING).last()
        self.assertIsNotNone(new_session)
        self.assertRedirects(response, reverse("lobby", args=[new_session.pin]))

    def test_create_lobby_for_draft_quiz(self):
        """Попытка создать лобби для черновика квиза перенаправляет."""
        draft_quiz = Quiz.objects.create(
            title='Draft', creator=self.teacher, status=Quiz.DRAFT
        )
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse('create_lobby', args=[draft_quiz.id])
        )
        self.assertRedirects(
            response, reverse('my_quizzes'), fetch_redirect_response=False
        )

    # --- lobby_view (для хоста) ---
    def test_lobby_view_get(self):
        """Хост видит страницу лобби с данными сессии."""
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse('lobby', args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['session'], self.session)

    def test_lobby_view_non_host(self):
        """Не-хост получает 404 при попытке просмотреть лобби."""
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('lobby', args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 404)

    # --- toggle_lock_view ---
    def test_toggle_lock_view(self):
        """Хост может переключить блокировку лобби."""
        self.client.force_login(self.teacher)
        self.assertFalse(self.session.is_locked)
        response = self.client.post(
            reverse('toggle_lock', args=[self.session.pin])
        )
        self.assertRedirects(response, reverse('lobby', args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_locked)

    # --- delete_session_view ---
    def test_delete_session_view(self):
        """Хост может удалить игровую сессию."""
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('delete_session', args=[self.session.pin])
        )
        self.assertRedirects(
            response, reverse('my_quizzes'), fetch_redirect_response=False
        )
        with self.assertRaises(GameSession.DoesNotExist):
            self.session.refresh_from_db()

    # --- realtime.build_player_list (бывший api_players) ---
    def test_build_player_list(self):
        """Сервис realtime отдаёт список игроков и статус блокировки."""
        from apps.main.services.realtime import build_player_list

        GameParticipant.objects.create(session=self.session, user=self.student)
        data = build_player_list(self.session)
        self.assertIn('players', data)
        self.assertEqual(len(data['players']), 1)
        self.assertEqual(data['players'][0]['username'], self.student.username)
        self.assertFalse(data['is_locked'])
        self.assertEqual(data['count'], 1)

    # --- join_lobby_view (для игрока) ---
    def test_join_lobby_view_success(self):
        """Студент успешно присоединяется к лобби по PIN."""
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'join_lobby.html')
        self.assertTrue(
            GameParticipant.objects.filter(
                session=self.session, user=self.student
            ).exists()
        )

    def test_join_lobby_view_when_already_joined(self):
        """Повторное присоединение не создаёт дубликатов."""
        GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            GameParticipant.objects.filter(
                session=self.session, user=self.student
            ).count(),
            1,
        )

    def test_join_lobby_view_host_redirect(self):
        """Хост перенаправляется в своё лобби при попытке присоединиться."""
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse('join_lobby', args=[self.session.pin])
        )
        self.assertRedirects(
            response, reverse('lobby', args=[self.session.pin])
        )

    # --- realtime.build_player_state (бывший api_state) ---
    def test_build_player_state_status(self):
        """Сервис realtime отдаёт состояние сессии для игрока."""
        from apps.main.services.realtime import build_player_state

        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        data = build_player_state(self.session, participant.id)
        self.assertEqual(data['status'], self.session.status)
        self.assertFalse(data['kicked'])

    def test_build_player_state_kicked(self):
        """Если участника нет, помечается kicked=True."""
        from apps.main.services.realtime import build_player_state

        data = build_player_state(self.session, 999999)
        self.assertTrue(data['kicked'])

    def test_build_player_state_includes_question(self):
        """Во время игры отдаются данные текущего вопроса."""
        from apps.main.services.realtime import build_player_state

        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = GameSession.IN_PROGRESS
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()

        data = build_player_state(self.session, participant.id)
        self.assertEqual(data['status'], GameSession.IN_PROGRESS)
        self.assertIsNotNone(data['question'])
        self.assertEqual(data['question']['index'], 0)
        self.assertIn('options', data['question'])
        self.assertFalse(data['has_answered'])

    # --- start_game_view ---
    def test_start_game_view_with_participants(self):
        """Хост начинает игру, если есть участники."""
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        response = self.client.post(
            reverse('start_game', args=[self.session.pin])
        )
        self.assertRedirects(
            response, reverse('lobby', args=[self.session.pin])
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'in_progress')

    def test_start_game_view_no_participants(self):
        """Без участников игра не начинается."""
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('start_game', args=[self.session.pin])
        )
        self.assertRedirects(
            response, reverse('lobby', args=[self.session.pin])
        )
        self.session.refresh_from_db()
        self.assertNotEqual(self.session.status, 'in_progress')

    def test_start_game_when_already_started(self):
        """Повторный старт не меняет статус."""
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = 'in_progress'
        self.session.save()
        response = self.client.post(
            reverse('start_game', args=[self.session.pin])
        )
        self.assertRedirects(
            response, reverse('lobby', args=[self.session.pin])
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'in_progress')

    # --- session_play_view (игровой процесс) ---
    def test_session_play_view_redirect_if_not_started(self):
        """Нельзя зайти на страницу игры, если она не началась."""
        self.client.force_login(self.student)
        GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        response = self.client.get(
            reverse('session_play', args=[self.session.pin])
        )
        self.assertRedirects(
            response, reverse('join_lobby', args=[self.session.pin])
        )

    def test_session_play_view_get_in_progress(self):
        """GET-запрос страницы игры во время активной сессии отображает вопрос."""
        self.client.force_login(self.student)
        GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = 'in_progress'
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()

        response = self.client.get(
            reverse('session_play', args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'session_play.html')
        # Проверяем, что переданный вопрос — созданный нами
        self.assertEqual(response.context['question'].id, self.question.id)

    def test_submit_answer_creates_game_answer(self):
        """POST submit_answer создаёт запись ответа и начисляет баллы."""
        self.client.force_login(self.student)
        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = 'in_progress'
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()

        # Сохраняем id участника в сессии клиента
        http_session = self.client.session
        http_session[f'lobby_participant_{self.session.pin}'] = participant.id
        http_session.save()

        data = {
            'answer': str(self.correct_answer.id),
            'timed_out': '0',
        }
        response = self.client.post(
            reverse('submit_answer', args=[self.session.pin]), data
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        game_answer = GameAnswer.objects.filter(
            participant=participant
        ).first()
        self.assertIsNotNone(game_answer)
        self.assertTrue(game_answer.is_correct)
        self.assertGreater(game_answer.points, 0)

    # --- quiz_sessions_list_view (для учителя) ---
    def test_quiz_sessions_list_view(self):
        """Учитель видит список сессий для своего квиза."""
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse('quiz_sessions_list', args=[self.quiz.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz_sessions_list.html')
        self.assertIn('sessions', response.context)

    # --- session_results_teacher_view (детальные результаты) ---
    def test_session_results_teacher_view(self):
        """Учитель видит детальные результаты по сессии."""
        self.client.force_login(self.teacher)
        participant = GameParticipant.objects.create(
            session=self.session, user=self.student, score=4
        )
        GameAnswer.objects.create(
            session=self.session,
            participant=participant,
            question=self.question,
            is_correct=True,
            points=4,
        )
        response = self.client.get(
            reverse('session_results_teacher', args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'session_results_teacher.html')
        self.assertIn('rows', response.context)
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(
            response.context['rows'][0]['user'], self.student
        )


class PreservationPropertyTest(TestCase):
    """Тесты сохранения существующего поведения лобби (Property 2: Preservation)."""

    @classmethod
    def setUpTestData(cls):
        """Создаёт пользователей и активный квиз."""
        cls.teacher = User.objects.create_user(
            username='teacher', password='testpass'
        )
        cls.student = User.objects.create_user(
            username='student', password='testpass'
        )
        cls.quiz = Quiz.objects.create(
            title='Test Quiz',
            creator=cls.teacher,
            status=Quiz.ACTIVE,
        )

    def setUp(self):
        self.client = Client()

    # --- Requirement 3.1: Normal exit via "Выйти" preserves delete + redirect ---
    def test_delete_session_view_deletes_and_redirects(self):
        """Preservation: delete_session_view POST удаляет сессию и редиректит."""
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='900001',
            status=GameSession.WAITING,
            is_locked=False,
        )
        session_id = session.id

        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('delete_session', args=[session.pin])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('my_quizzes'), response.url)
        self.assertFalse(GameSession.objects.filter(id=session_id).exists())

    # --- Requirement 3.2: Non-participant on IN_PROGRESS session gets error ---
    def test_join_lobby_non_participant_in_progress_gets_error(self):
        """Preservation: не-участник на IN_PROGRESS сессии получает ошибку."""
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='900002',
            status=GameSession.IN_PROGRESS,
            is_locked=False,
            current_question=0,
            current_question_started_at=timezone.now(),
        )

        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[session.pin])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lobby_error.html')
        self.assertContains(response, 'Игра уже началась или завершена')

    # --- Requirement 3.3: Locked lobby blocks new players ---
    def test_join_lobby_locked_session_blocks_player(self):
        """Preservation: закрытое лобби блокирует новых игроков."""
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='900003',
            status=GameSession.WAITING,
            is_locked=True,
        )

        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[session.pin])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lobby_error.html')
        self.assertContains(response, 'Лобби закрыто для новых игроков')

    # --- Requirement 3.4: Full lobby blocks new players ---
    def test_join_lobby_full_session_blocks_player(self):
        """Preservation: полное лобби блокирует новых игроков."""
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='900004',
            status=GameSession.WAITING,
            is_locked=False,
        )

        for i in range(25):
            user = User.objects.create_user(
                username=f'filler_user_{i}', password='testpass'
            )
            GameParticipant.objects.create(session=session, user=user)

        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[session.pin])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lobby_error.html')
        self.assertContains(response, 'Лобби заполнено (максимум 25 игроков)')

    # --- Requirement 3.5: Normal lobby creation (no orphans) works ---
    def test_create_lobby_no_orphans_creates_session_normally(self):
        """Preservation: создание лобби без осиротевших сессий работает нормально."""
        active_quiz = Quiz.objects.create(
            title='Active Quiz', creator=self.teacher, status=Quiz.ACTIVE
        )

        GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING
        ).delete()

        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse('create_lobby', args=[active_quiz.id])
        )

        self.assertEqual(response.status_code, 302)
        new_session = GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING, quiz=active_quiz
        ).first()
        self.assertIsNotNone(new_session)
        self.assertIn(
            reverse('lobby', args=[new_session.pin]), response.url
        )

    # --- Requirement 3.6: Player joining WAITING session gets GameParticipant ---
    def test_join_lobby_waiting_session_creates_participant(self):
        """Preservation: игрок входит в WAITING сессию — создаётся GameParticipant."""
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='900006',
            status=GameSession.WAITING,
            is_locked=False,
        )

        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[session.pin])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'join_lobby.html')
        self.assertTrue(
            GameParticipant.objects.filter(
                session=session, user=self.student
            ).exists()
        )


class BugConditionExplorationTest(TestCase):
    """Тесты исследования баг-условий (очистка осиротевших сессий и переподключение)."""

    @classmethod
    def setUpTestData(cls):
        """Создаёт пользователей и активный квиз."""
        cls.teacher = User.objects.create_user(
            username='teacher', password='testpass'
        )
        cls.student = User.objects.create_user(
            username='student', password='testpass'
        )
        cls.quiz = Quiz.objects.create(
            title='Test Quiz',
            creator=cls.teacher,
            status=Quiz.ACTIVE,
        )

    def setUp(self):
        self.client = Client()
        # На всякий случай убеждаемся, что квиз активен (уже из setUpTestData)
        self.quiz.status = Quiz.ACTIVE
        self.quiz.save()

    def test_create_lobby_deletes_existing_waiting_session(self):
        """Баг: старая WAITING сессия не удаляется при создании нового лобби."""
        old_session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='111111',
            status=GameSession.WAITING,
            is_locked=False,
        )
        old_session_id = old_session.id

        self.client.force_login(self.teacher)
        self.client.get(reverse('create_lobby', args=[self.quiz.id]))

        self.assertFalse(
            GameSession.objects.filter(id=old_session_id).exists(),
            'Старая WAITING сессия не была удалена при создании нового лобби.',
        )

    def test_join_lobby_redirects_existing_participant_to_session_play(self):
        """Баг: существующий участник не редиректится на session_play в IN_PROGRESS."""
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='222222',
            status=GameSession.IN_PROGRESS,
            is_locked=False,
            current_question=0,
            current_question_started_at=timezone.now(),
        )

        GameParticipant.objects.create(session=session, user=self.student)

        self.client.force_login(self.student)
        response = self.client.get(
            reverse('join_lobby', args=[session.pin])
        )

        self.assertEqual(
            response.status_code,
            302,
            'Ожидался редирект на session_play для существующего участника.',
        )
        self.assertIn(
            reverse('session_play', args=[session.pin]), response.url
        )

    def test_create_lobby_deletes_all_orphaned_waiting_sessions(self):
        """Баг: несколько старых WAITING сессий не удаляются при создании нового лобби."""
        session1 = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='333333',
            status=GameSession.WAITING,
            is_locked=False,
        )
        session2 = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin='444444',
            status=GameSession.WAITING,
            is_locked=False,
        )
        old_ids = [session1.id, session2.id]

        self.client.force_login(self.teacher)
        self.client.get(reverse('create_lobby', args=[self.quiz.id]))

        remaining = GameSession.objects.filter(id__in=old_ids).count()
        self.assertEqual(remaining, 0, 'Не все старые WAITING сессии были удалены.')

        waiting_sessions = GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING
        )
        self.assertEqual(
            waiting_sessions.count(),
            1,
            'После создания нового лобби должна остаться ровно одна WAITING сессия.',
        )


class TestProfile(TestCase):
    """Тесты для модели Profile и связанных сигналов."""

    def test_profile_creation_signal_for_new_user(self):
        """
        Проверка: при создании нового пользователя автоматически создаётся профиль
        с ролью STUDENT (если имя не 'administration').
        """
        user = User.objects.create(username="newuser")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.role, Profile.STUDENT)

    def test_admin_profile_auto_created_as_admin(self):
        """
        Проверка: пользователь с именем 'administration' получает профиль с ролью ADMIN.
        """
        admin = User.objects.create(username="administration")
        self.assertEqual(admin.profile.role, Profile.ADMIN)
        self.assertTrue(admin.profile.is_admin)

    def test_save_signal_corrects_role_for_admin_username(self):
        """
        Проверка: при сохранении пользователя с именем 'administration' его профиль
        принудительно становится ADMIN (даже если была изменена роль).
        """
        # Создаём или получаем пользователя с именем "administration"
        admin_user, _ = User.objects.get_or_create(
            username="administration", defaults={"email": ""}
        )
        # Пытаемся изменить роль на STUDENT
        admin_user.profile.role = Profile.STUDENT
        admin_user.profile.is_admin = False
        admin_user.profile.save()
        admin_user.save()  # сигнал должен восстановить права
        admin_user.refresh_from_db()
        self.assertEqual(admin_user.profile.role, Profile.ADMIN)
        self.assertTrue(admin_user.profile.is_admin)


class TestQuiz(TestCase):
    """Тесты для модели Quiz и её методов."""

    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username="teacher", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Test Quiz", creator=cls.host, status=Quiz.ACTIVE
        )
        # Вопрос с коэффициентом 1 (multiple) для проверки max_score = 4
        cls.question = Question.objects.create(
            quiz=cls.quiz,
            text="Sample question",
            question_type="multiple",
            coefficient=1,
            order=1,
        )

    def test_total_questions_no_revision(self):
        """Метод total_questions() возвращает количество вопросов текущей ревизии."""
        self.assertEqual(self.quiz.total_questions(), 1)

    def test_total_questions_with_revision(self):
        """Если у квиза есть текущая ревизия, total_questions() берёт question_count из неё."""
        rev = QuizRevision.objects.create(
            quiz=self.quiz, version=1, title="v1", question_count=3, max_score=12
        )
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(self.quiz.total_questions(), 3)

    def test_total_max_score_no_revision(self):
        """Метод total_max_score() считает сумму коэффициентов вопросов, умноженных на 4."""
        # question type 'multiple' coefficient=1 -> 4*1=4
        self.assertEqual(self.quiz.total_max_score(), 4)

    def test_total_max_score_with_revision(self):
        """Если есть текущая ревизия, total_max_score() берёт max_score из неё."""
        rev = QuizRevision.objects.create(
            quiz=self.quiz, version=1, title="v1", max_score=20
        )
        self.quiz.current_revision = rev
        self.quiz.save()
        self.assertEqual(self.quiz.total_max_score(), 20)

    def test_str_method(self):
        """Строковое представление квиза — его заголовок."""
        self.assertEqual(str(self.quiz), "Test Quiz")


class TestGameSession(TestCase):
    """Тесты для модели GameSession (игровая сессия)."""

    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username="host_user", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Session Quiz", creator=cls.host, status=Quiz.ACTIVE
        )
        # Создаём базовую сессию для теста test_str_contains_pin
        cls.session = GameSession.objects.create(
            quiz=cls.quiz, host=cls.host, pin="123456", status=GameSession.WAITING
        )

    def test_pin_generated_on_creation(self):
        """При создании игровой сессии генерируется 6-значный PIN-код."""
        # Создаём новую сессию без указания pin, чтобы сработала авто-генерация
        session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertIsNotNone(session.pin)
        self.assertEqual(len(session.pin), 6)
        self.assertTrue(session.pin.isdigit())

    def test_default_status_is_waiting(self):
        """По умолчанию статус сессии — 'waiting' (ожидание игроков)."""
        session = GameSession.objects.create(quiz=self.quiz, host=self.host)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_str_contains_pin(self):
        """Строковое представление сессии содержит её PIN-код."""
        self.assertIn(self.session.pin, str(self.session))


class TestGameParticipant(TestCase):
    """Тесты для модели GameParticipant (участник игровой сессии)."""

    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username="host", password="testpass")
        cls.player = User.objects.create_user(username="player", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Participant Quiz", creator=cls.host, status=Quiz.ACTIVE
        )
        cls.session = GameSession.objects.create(
            quiz=cls.quiz, host=cls.host, pin="654321", status=GameSession.WAITING
        )

    def test_default_values(self):
        """Проверка значений по умолчанию: score=0, is_answered=False, joined_at заполняется."""
        participant = GameParticipant.objects.create(
            session=self.session, user=self.player
        )
        self.assertEqual(participant.score, 0)
        self.assertFalse(participant.is_answered)
        self.assertIsNotNone(participant.joined_at)


class TestAnswer(TestCase):
    """Тесты для модели Answer (вариант ответа на вопрос)."""

    @classmethod
    def setUpTestData(cls):
        host = User.objects.create_user(username="quiz_author", password="testpass")
        quiz = Quiz.objects.create(
            title="Answer Quiz", creator=host, status=Quiz.ACTIVE
        )
        question = Question.objects.create(
            quiz=quiz, text="Q", question_type="single", coefficient=1, order=1
        )
        cls.correct_answer = Answer.objects.create(
            question=question, text="Right", is_correct=True
        )
        cls.wrong_answer = Answer.objects.create(
            question=question, text="Wrong", is_correct=False
        )

    def test_answer_correctness_flag(self):
        """Флаг is_correct корректно отражает правильность варианта ответа."""
        self.assertTrue(self.correct_answer.is_correct)
        self.assertFalse(self.wrong_answer.is_correct)


class TestQuizRevision(TestCase):
    """Тесты для модели QuizRevision (версия квиза)."""

    @classmethod
    def setUpTestData(cls):
        host = User.objects.create_user(username="revision_author", password="testpass")
        cls.quiz = Quiz.objects.create(
            title="Revision Quiz", creator=host, status=Quiz.ACTIVE
        )

    def test_creation_and_ordering(self):
        """Ревизии одного квиза упорядочиваются по убыванию номера версии."""
        rev1 = QuizRevision.objects.create(quiz=self.quiz, version=1, title="v1")
        rev2 = QuizRevision.objects.create(quiz=self.quiz, version=2, title="v2")
        revisions = self.quiz.revisions.order_by("-version")
        self.assertEqual(list(revisions), [rev2, rev1])


class TestQuizResult(TestCase):
    """Тесты для модели QuizResult (результат прохождения квиза)."""

    def test_str_method_returns_score(self):
        """Строковое представление результата — это набранный балл."""
        result = QuizResult(user_id=1, quiz_id=1, score=10)
        self.assertEqual(str(result), "10")
