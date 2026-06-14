import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.main.services import realtime
from apps.main.services.guest_cleanup import (
    resolve_display_name_from_user,
    cleanup_guest_users,
)
from apps.main.services.quiz_revisions import (
    get_current_revision,
    get_session_questions,
    get_session_max_score,
)
from apps.main.services.quiz_scoring import score_question
from apps.quiz.models import Quiz, QuizResult, GameSession, GameParticipant, GameAnswer


# Create your views here.
def _get_guest_username(
    guest_name: str | None, exclude_user_id: int | None = None
) -> str:
    """Формирует уникальное имя гостя на основе ника или случайного идентификатора."""
    if guest_name:
        cleaned = "".join(
            ch if ch.isalnum() or ch in "_-" else "_" for ch in guest_name.strip()
        )
        cleaned = cleaned.strip("_-")[:120]
        if cleaned:
            username = f"guest_{cleaned}"
        else:
            username = None
    else:
        username = None

    if not username:
        username = f"guest_{uuid.uuid4().hex[:8]}"

    original = username
    counter = 1
    conflict_query = User.objects.filter(username=username)
    if exclude_user_id is not None:
        conflict_query = conflict_query.exclude(pk=exclude_user_id)
    while conflict_query.exists():
        username = f"{original}_{counter}"
        counter += 1
        conflict_query = User.objects.filter(username=username)
        if exclude_user_id is not None:
            conflict_query = conflict_query.exclude(pk=exclude_user_id)

    return username


def _get_request_user(request, guest_name=None):
    """Возвращает пользователя для игры: реального или гостевого."""
    if request.user.is_authenticated:
        return request.user

    guest_user = None
    guest_user_id = request.session.get("guest_user_id")
    if guest_user_id:
        try:
            guest_user = User.objects.get(pk=guest_user_id)
        except User.DoesNotExist:
            request.session.pop("guest_user_id", None)
            guest_user = None

    if guest_user is not None:
        if guest_name:
            new_username = _get_guest_username(
                guest_name, exclude_user_id=guest_user.id
            )
            if new_username != guest_user.username:
                guest_user.username = new_username
                guest_user.save()
        return guest_user

    username = _get_guest_username(guest_name)
    guest_user = User.objects.create_user(username=username)
    request.session["guest_user_id"] = guest_user.id
    return guest_user


logger = logging.getLogger(__name__)


@login_required(login_url="login_page")
def create_lobby_view(request, quiz_id):
    """Создание лобби по текущей ревизии квиза."""
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user, is_deleted=False)

    if quiz.status == Quiz.DRAFT:
        return redirect("my_quizzes")

    # Clean up all expired WAITING sessions (older than 1 hour)
    expiry_threshold = timezone.now() - timezone.timedelta(hours=1)
    GameSession.objects.filter(
        status=GameSession.WAITING, created_at__lt=expiry_threshold
    ).delete()

    # Delete all WAITING sessions for this host
    GameSession.objects.filter(host=request.user, status=GameSession.WAITING).delete()

    session = GameSession.objects.create(
        quiz=quiz,
        revision=get_current_revision(quiz),
        host=request.user,
    )
    logger.info(
        "Пользователь %s создал лобби для квиза «%s» (PIN: %s) (IP: %s)",
        request.user.username,
        quiz.title,
        session.pin,
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("lobby", pin=session.pin)


@login_required(login_url="login_page")
def lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)

    # Auto-expire WAITING sessions older than 1 hour
    if session.status == GameSession.WAITING:
        expiry_threshold = timezone.now() - timezone.timedelta(hours=1)
        if session.created_at < expiry_threshold:
            session.delete()
            return redirect("my_quizzes")

    return render(request, "lobby.html", {"session": session})


@login_required(login_url="login_page")
@require_POST
def toggle_lock_view(request, pin):
    """Закрытие/открытие возможности присоединиться к сессии"""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    session.is_locked = not session.is_locked
    session.save()
    realtime.broadcast_lobby_changed(pin)
    logger.info(
        "Пользователь %s %s лобби %s (PIN: %s) (IP: %s)",
        request.user.username,
        "закрыл" if session.is_locked else "открыл",
        session.quiz.title,
        pin,
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("lobby", pin=pin)


@login_required(login_url="login_page")
@require_POST
def delete_session_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    quiz_title = session.quiz.title
    session.delete()
    logger.info(
        "Пользователь %s удалил лобби с PIN %s (квиз «%s») (IP: %s)",
        request.user.username,
        pin,
        quiz_title,
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("my_quizzes")


@login_required(login_url="login_page")
@require_POST
def kick_player_view(request, pin, participant_id):
    """Кик игрока из лобби хостом."""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    participant = get_object_or_404(GameParticipant, id=participant_id, session=session)
    display_name = participant.get_display_name()
    participant.delete()
    realtime.broadcast_player_kicked(pin, participant_id)
    logger.info(
        "Хост %s выгнал игрока '%s' из лобби %s (IP: %s)",
        request.user.username,
        display_name,
        pin,
        request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"success": True})


def join_lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)

    # Для завершённых сессий не создаём нового гостя — показываем ошибку
    if session.status == GameSession.FINISHED:
        return render(request, "lobby_error.html", {"message": "Игра уже завершена."})

    if not request.user.is_authenticated:
        # Проверяем, пришли ли мы через ввод кода или по прямой ссылке
        from_code = request.GET.get("from_code") == "1"
        guest_nickname_set = request.session.get("guest_nickname_set")

        # Если пришли по прямой ссылке (не через from_code) или ник не был установлен
        if not from_code and not guest_nickname_set:
            # Очищаем старого гостя и требуем ввод нового ника при заходе по ссылке
            request.session.pop("guest_user_id", None)
            request.session.pop("guest_nickname_set", None)
            return redirect(f"{reverse('main_page')}?pin={pin}&highlight=1")

        # Если пришли через код, очищаем флаг для следующего раза
        if from_code:
            request.session.pop("guest_nickname_set", None)

    current_user = _get_request_user(request)

    # Auto-expire WAITING sessions older than 1 hour
    if session.status == GameSession.WAITING:
        expiry_threshold = timezone.now() - timezone.timedelta(hours=1)
        if session.created_at < expiry_threshold:
            session.delete()
            return render(
                request,
                "lobby_error.html",
                {"message": "Это лобби истекло и было закрыто."},
            )

    if session.host == current_user:
        return redirect("lobby", pin=pin)

    if (
        session.status == GameSession.IN_PROGRESS
        and GameParticipant.objects.filter(session=session, user=current_user).exists()
    ):
        return redirect("session_play", pin=pin)

    if session.status != GameSession.WAITING:
        return render(
            request, "lobby_error.html", {"message": "Игра уже началась или завершена."}
        )

    if session.is_locked:
        return render(
            request, "lobby_error.html", {"message": "Лобби закрыто для новых игроков."}
        )

    if session.participants.count() >= 25:
        return render(
            request,
            "lobby_error.html",
            {"message": "Лобби заполнено (максимум 25 игроков)."},
        )

    participant, created = GameParticipant.objects.get_or_create(
        session=session, user=current_user
    )
    if created:
        # Сохраняем отображаемое имя при создании участника
        participant.display_name = resolve_display_name_from_user(current_user)
        participant.save()

    # Сохраняем ID участника в HTTP-сессии, чтобы после удаления гостя
    # можно было показать результаты
    request.session[f"lobby_participant_{pin}"] = participant.id

    if created:
        realtime.broadcast_lobby_changed(pin)

    logger.info(
        "Игрок %s присоединился к лобби %s (квиз «%s», хост: %s) (IP: %s)",
        request.user.username,
        pin,
        session.quiz.title,
        session.host.username,
        request.META.get("REMOTE_ADDR"),
    )
    return render(
        request, "join_lobby.html", {"session": session, "participant": participant}
    )


@login_required(login_url="login_page")
@require_POST
def start_game_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    if session.participants.count() == 0:
        logger.warning(
            "Пользователь %s попытался начать игру в лобби %s, но нет участников (IP: %s)",
            request.user.username,
            pin,
            request.META.get("REMOTE_ADDR"),
        )
        return redirect("lobby", pin=pin)
    session.status = GameSession.IN_PROGRESS
    session.current_question_started_at = timezone.now()
    session.save()
    realtime.broadcast_game_started(pin)
    logger.info(
        "Пользователь %s начал игру в лобби %s (квиз «%s», участников: %d) (IP: %s)",
        request.user.username,
        pin,
        session.quiz.title,
        session.participants.count(),
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("lobby", pin=pin)


def session_play_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)

    # Сначала пробуем найти участника по сохранённому ID в HTTP-сессии,
    # чтобы не создавать нового гостя после удаления старого
    participant = None
    current_user = None

    stored_participant_id = request.session.get(f"lobby_participant_{pin}")
    if stored_participant_id:
        participant = GameParticipant.objects.filter(
            id=stored_participant_id,
            session=session,
        ).first()

    if participant is None:
        current_user = _get_request_user(request)
        participant = GameParticipant.objects.filter(
            session=session,
            user=current_user,
        ).first()

    if current_user is None:
        # Участник найден по stored ID, определяем current_user для дальнейшей логики
        if participant and participant.user:
            current_user = participant.user
        elif request.user.is_authenticated:
            current_user = request.user

    if participant is None:
        return redirect("join_lobby", pin=pin)

    # Гарантируем, что ID участника сохранён в HTTP-сессии
    request.session.setdefault(f"lobby_participant_{pin}", participant.id)

    questions = get_session_questions(session)
    total = len(questions)
    total_max_score = get_session_max_score(session)

    if not questions:
        return render(
            request,
            "lobby_error.html",
            {
                "message": "В этой сессии нет вопросов.",
            },
        )

    if session.status == GameSession.FINISHED or session.current_question >= total:
        result_session_key = f"lobby_result_{pin}"
        result_id = request.session.get(result_session_key)
        score_percent = (
            participant.score / total_max_score * 100 if total_max_score else 0
        )

        if result_id is not None:
            QuizResult.objects.filter(
                id=result_id,
                user=current_user,
            ).update(
                score=participant.score,
                max_score=total_max_score,
                score_percent=score_percent,
                completed=True,
                completed_at=timezone.now(),
            )

        return render(
            request,
            "session_results.html",
            {
                "session": session,
                "participant": participant,
                "max_score": total_max_score,
            },
        )

    if session.status != GameSession.IN_PROGRESS:
        return redirect("join_lobby", pin=pin)

    result_session_key = f"lobby_result_{pin}"
    result_id = request.session.get(result_session_key)

    if result_id is None:
        result = QuizResult.objects.create(
            user=current_user,
            quiz=session.quiz,
            revision=session.revision,
            score=0,
            max_score=total_max_score,
            score_percent=0,
            completed=False,
            display_name=resolve_display_name_from_user(current_user),
        )
        request.session[result_session_key] = result.id

    question = questions[session.current_question]
    question_started_at = session.current_question_started_at or timezone.now()
    elapsed_seconds = int((timezone.now() - question_started_at).total_seconds())
    remaining_seconds = max(0, question.time_limit - elapsed_seconds)

    # Защита от рассинхрона: если is_answered=True, но реального ответа
    # на текущий вопрос нет — игрок завис в ожидании пока учитель перешёл.
    # Сбрасываем флаг чтобы игрок мог ответить на актуальный вопрос.
    if participant.is_answered:
        answer_check = {"session": session, "participant": participant}
        if session.revision_id:
            answer_check["revision_question"] = question
        else:
            answer_check["question"] = question
        has_real_answer = GameAnswer.objects.filter(**answer_check).exists()
        if not has_real_answer:
            participant.is_answered = False
            participant.save()

    # Единый экран игры: одна страница на всю игру, одно WebSocket-соединение.
    # Вопросы, экран ожидания и таймер переключаются на месте через WS —
    # без перезагрузок страницы (и, соответственно, без пересоздания сокета).
    response = render(
        request,
        "session_play.html",
        {
            "session": session,
            "question": question,
            "participant": participant,
            "index": session.current_question,
            "total": total,
            "answered": participant.is_answered,
            "remaining_seconds": remaining_seconds,
            "submit_url": reverse("submit_answer", args=[pin]),
        },
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@require_POST
def submit_answer_view(request, pin):
    """JSON-эндпоинт: игрок отправляет ответ на текущий вопрос.

    Вызывается через fetch с единого экрана игры — БЕЗ перезагрузки
    страницы, поэтому WebSocket-соединение игрока не пересоздаётся.
    """
    session = get_object_or_404(GameSession, pin=pin)

    # Находим участника по сохранённому ID в HTTP-сессии.
    participant = None
    stored_participant_id = request.session.get(f"lobby_participant_{pin}")
    if stored_participant_id:
        participant = GameParticipant.objects.filter(
            id=stored_participant_id, session=session
        ).first()
    if participant is None:
        return JsonResponse(
            {"success": False, "error": "Участник не найден"}, status=403
        )

    if session.status != GameSession.IN_PROGRESS:
        return JsonResponse({"success": False, "error": "Игра не активна"}, status=400)

    questions = get_session_questions(session)
    total = len(questions)
    if not (0 <= session.current_question < total):
        return JsonResponse(
            {"success": False, "error": "Нет активного вопроса"}, status=400
        )

    question = questions[session.current_question]
    question_started_at = session.current_question_started_at or timezone.now()
    elapsed_seconds = int((timezone.now() - question_started_at).total_seconds())
    server_timed_out = (question.time_limit - elapsed_seconds) <= 0

    answer_lookup = {"session": session, "participant": participant}
    if session.revision_id:
        answer_lookup["revision_question"] = question
    else:
        answer_lookup["question"] = question

    # Уже ответил на этот вопрос — считаем успехом (идемпотентность).
    if GameAnswer.objects.filter(**answer_lookup).exists():
        return JsonResponse({"success": True, "already_answered": True})

    timed_out = request.POST.get("timed_out") == "1" or server_timed_out

    score_result = score_question(question, request, timed_out=timed_out)
    earned_points = score_result.points
    is_correct = score_result.is_correct

    participant.score += earned_points
    participant.is_answered = True
    participant.save()

    game_answer_data = {
        "session": session,
        "participant": participant,
        "is_correct": is_correct,
        "points": earned_points,
    }
    if session.revision_id:
        game_answer_data["revision_question"] = question
    else:
        game_answer_data["question"] = question
    GameAnswer.objects.create(**game_answer_data)

    logger.info(
        "Игрок %s в лобби %s (квиз «%s») ответил на вопрос %d. Верно: %s, баллов: %d (IP: %s)",
        request.user.username if request.user.is_authenticated else "guest",
        pin,
        session.quiz.title,
        session.current_question + 1,
        "да" if is_correct else "нет",
        earned_points,
        request.META.get("REMOTE_ADDR"),
    )

    total_participants = session.participants.count()
    answered_count = session.participants.filter(is_answered=True).count()
    if answered_count >= total_participants:
        session.ready_for_next_question = True
        session.save()
        if session.status == GameSession.FINISHED:
            cleanup_guest_users(session)

    # Уведомляем хоста об изменении статистики (новый ответ).
    realtime.broadcast_stats_changed(pin)

    return JsonResponse({"success": True, "score": participant.score})


@login_required
def quiz_sessions_list_view(request, quiz_id):
    """Список всех сессий квиза для учителя (история прохождений)"""
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user, is_deleted=False)
    sessions = quiz.sessions.all().order_by("-created_at")
    return render(
        request,
        "quiz_sessions_list.html",
        {
            "quiz": quiz,
            "sessions": sessions,
        },
    )


@login_required(login_url="login_page")
def advance_question_view(request, pin):
    """API: учитель переводит игру на следующий вопрос.

    Если кто-то из участников не успел ответить (игнорировал вопрос),
    им автоматически засчитывается неверный ответ с 0 очков, и игра
    продолжается без ожидания.
    """
    session = get_object_or_404(GameSession, pin=pin, host=request.user)

    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Метод не разрешён"}, status=405
        )

    if session.status == GameSession.FINISHED:
        return JsonResponse(
            {"success": False, "error": "Игра уже завершена"}, status=400
        )

    questions = get_session_questions(session)
    total_questions = len(questions)
    current_q_index = session.current_question

    if 0 <= current_q_index < total_questions:
        current_question = questions[current_q_index]

        # Авто-засчитываем неверный ответ всем, кто не ответил
        unanswered_participants = session.participants.filter(is_answered=False)
        for participant in unanswered_participants:
            answer_lookup = {"session": session, "participant": participant}
            if session.revision_id:
                answer_lookup["revision_question"] = current_question
            else:
                answer_lookup["question"] = current_question

            already_answered = GameAnswer.objects.filter(**answer_lookup).exists()
            if not already_answered:
                game_answer_data = {
                    "session": session,
                    "participant": participant,
                    "is_correct": False,
                    "points": 0,
                }
                if session.revision_id:
                    game_answer_data["revision_question"] = current_question
                else:
                    game_answer_data["question"] = current_question

                GameAnswer.objects.create(**game_answer_data)
                participant.is_answered = True
                participant.save()

                logger.info(
                    "Игрок %s в лобби %s (квиз «%s») не ответил на вопрос %d — засчитан пропуск (IP: %s)",
                    participant.user.username if participant.user else "unknown",
                    pin,
                    session.quiz.title,
                    current_q_index + 1,
                    request.META.get("REMOTE_ADDR"),
                )

    # Переходим к следующему вопросу
    session.participants.update(is_answered=False)
    session.ready_for_next_question = False
    session.current_question += 1

    if session.current_question >= total_questions:
        session.status = GameSession.FINISHED
        session.current_question_started_at = None
        cleanup_guest_users(session)
    else:
        session.current_question_started_at = timezone.now()

    session.save()

    realtime.broadcast_question_advanced(pin)

    logger.info(
        "Учитель %s перешёл к вопросу %d в лобби %s (IP: %s)",
        request.user.username,
        session.current_question + 1,
        pin,
        request.META.get("REMOTE_ADDR"),
    )

    return JsonResponse(
        {
            "success": True,
            "current_question": session.current_question,
        }
    )


@login_required(login_url="login_page")
def session_results_teacher_view(request, pin):
    """Детальные результаты сессии для учителя: таблица участник × вопрос."""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)

    questions = get_session_questions(session)
    max_score = get_session_max_score(session)

    for question in questions:
        question.options = [
            {
                "letter": chr(65 + idx),
                "text": opt.text,
                "is_correct": opt.is_correct,
            }
            for idx, opt in enumerate(question.answers.all())
        ]
        question.is_number_type = question.question_type == "number"
        question.is_text_type = question.question_type == "text"

    participants = list(session.participants.select_related("user").order_by("-score"))

    if session.revision_id:
        answers_qs = GameAnswer.objects.filter(session=session).values(
            "participant_id",
            "revision_question_id",
            "is_correct",
            "points",
        )
        question_key_name = "revision_question_id"
    else:
        answers_qs = GameAnswer.objects.filter(session=session).values(
            "participant_id",
            "question_id",
            "is_correct",
            "points",
        )
        question_key_name = "question_id"

    answers_map = {}
    for game_answer in answers_qs:
        participant_answers = answers_map.setdefault(game_answer["participant_id"], {})
        participant_answers[game_answer[question_key_name]] = {
            "is_correct": game_answer["is_correct"],
            "points": game_answer["points"],
        }

    rows = []
    for rank, participant in enumerate(participants, start=1):
        q_results = []

        for question in questions:
            answer_data = answers_map.get(participant.id, {}).get(question.id)

            if answer_data is None:
                q_results.append(None)
                continue

            q_results.append(
                {
                    "points": answer_data["points"],
                    "max_points": (
                        0
                        if question.question_type == "text"
                        else 4 * question.coefficient
                    ),
                    "is_correct": answer_data["is_correct"],
                }
            )

        rows.append(
            {
                "rank": rank,
                "user": participant.user,
                "display_name": participant.get_display_name(),
                "score": participant.score,
                "max_score": max_score,
                "q_results": q_results,
            }
        )

    return render(
        request,
        "session_results_teacher.html",
        {
            "session": session,
            "questions": questions,
            "rows": rows,
        },
    )


class LobbyViewsTest(TestCase):
    """Набор тестов для всех представлений, связанных с игровым лобби."""

    fixtures = ["db.json"]

    def setUp(self):
        """Настройка тестового окружения: создание клиента,
        пользователей, квиза и игровой сессии."""
        self.client = Client()
        self.teacher = User.objects.get(pk=2)
        self.student = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)  # активный
        self.session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="123456",
            status=GameSession.WAITING,
            is_locked=False,
        )

    # --- create_lobby_view ---
    def test_create_lobby_view(self):
        """Проверка: учитель может создать лобби для активного квиза,
        после чего перенаправляется на список своих квизов."""
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("create_lobby", args=[self.quiz.id]))
        self.assertRedirects(
            response, reverse("my_quizzes"), fetch_redirect_response=False
        )
        session = GameSession.objects.filter(quiz=self.quiz, host=self.teacher).last()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, GameSession.WAITING)

    def test_create_lobby_for_draft_quiz(self):
        """Проверка: попытка создать лобби для черновика квиза
        также перенаправляет на список квизов (без создания сессии?)."""
        draft_quiz = Quiz.objects.create(
            title="Draft", creator=self.teacher, status=Quiz.DRAFT
        )
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("create_lobby", args=[draft_quiz.id]))
        self.assertRedirects(
            response, reverse("my_quizzes"), fetch_redirect_response=False
        )

    # --- lobby_view (для хоста) ---
    def test_lobby_view_get(self):
        """GET-запрос к странице лобби от хоста
        возвращает страницу с данными сессии."""
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["session"], self.session)

    def test_lobby_view_non_host(self):
        """Проверка: студент (не создатель лобби) не может просматривать лобби, получает 404."""
        self.client.force_login(self.student)
        response = self.client.get(reverse("lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 404)

    # --- toggle_lock_view ---
    def test_toggle_lock_view(self):
        """Проверка: хост может переключить блокировку лобби
        (запрет на вход новых игроков)."""
        self.client.force_login(self.teacher)
        self.assertFalse(self.session.is_locked)
        response = self.client.post(reverse("toggle_lock", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_locked)

    # --- delete_session_view ---
    def test_delete_session_view(self):
        """Проверка: хост может удалить игровую сессию,
        после чего она исчезает из БД."""
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("delete_session", args=[self.session.pin]))
        self.assertRedirects(
            response, reverse("my_quizzes"), fetch_redirect_response=False
        )
        with self.assertRaises(GameSession.DoesNotExist):
            self.session.refresh_from_db()

    # --- realtime.build_player_list (бывший api_players) ---
    def test_build_player_list(self):
        """Сервис realtime отдаёт список игроков и статус блокировки
        (раньше это был HTTP-эндпоинт api_players, теперь — push по WS)."""
        from apps.main.services.realtime import build_player_list

        GameParticipant.objects.create(session=self.session, user=self.student)
        data = build_player_list(self.session)
        self.assertIn("players", data)
        self.assertEqual(len(data["players"]), 1)
        self.assertEqual(data["players"][0]["username"], self.student.username)
        self.assertFalse(data["is_locked"])
        self.assertEqual(data["count"], 1)

    # --- join_lobby_view (для игрока) ---
    def test_join_lobby_view_success(self):
        """Проверка: студент может успешно присоединиться к лобби по PIN-коду."""
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "join_lobby.html")
        self.assertTrue(
            GameParticipant.objects.filter(
                session=self.session, user=self.student
            ).exists()
        )

    def test_join_lobby_view_when_already_joined(self):
        """Если студент уже присоединился,
        повторное присоединение не создаёт дубликата."""
        GameParticipant.objects.create(session=self.session, user=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            GameParticipant.objects.filter(
                session=self.session, user=self.student
            ).count(),
            1,
        )

    def test_join_lobby_view_host_redirect(self):
        """Хост, пытающийся присоединиться к своему же лобби,
        перенаправляется на страницу управления лобби."""
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("join_lobby", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))

    # --- realtime.build_player_state (бывший api_state) ---
    def test_build_player_state_status(self):
        """Сервис realtime отдаёт состояние сессии для игрока,
        включая текущий статус (раньше — HTTP-эндпоинт api_state)."""
        from apps.main.services.realtime import build_player_state

        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        data = build_player_state(self.session, participant.id)
        self.assertEqual(data["status"], self.session.status)
        self.assertFalse(data["kicked"])

    def test_build_player_state_kicked(self):
        """Если участника нет в сессии, build_player_state помечает kicked=True."""
        from apps.main.services.realtime import build_player_state

        data = build_player_state(self.session, 999999)
        self.assertTrue(data["kicked"])

    def test_build_player_state_includes_question(self):
        """Во время игры build_player_state отдаёт данные текущего вопроса,
        чтобы игрок мог отрисовать его без перезагрузки страницы."""
        from apps.main.services.realtime import build_player_state

        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = GameSession.IN_PROGRESS
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()

        data = build_player_state(self.session, participant.id)
        self.assertEqual(data["status"], GameSession.IN_PROGRESS)
        self.assertIsNotNone(data["question"])
        self.assertEqual(data["question"]["index"], 0)
        self.assertIn("options", data["question"])
        self.assertFalse(data["has_answered"])

    # --- start_game_view ---
    def test_start_game_view_with_participants(self):
        """Хост может начать игру, если в лобби есть хотя бы один участник."""
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(session=self.session, user=self.student)
        response = self.client.post(reverse("start_game", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "in_progress")

    def test_start_game_view_no_participants(self):
        """Если в лобби нет участников,
        игра не начинается (статус не меняется)."""
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("start_game", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertNotEqual(self.session.status, "in_progress")

    def test_start_game_when_already_started(self):
        """Повторный запрос на старт уже запущенной игры не меняет статус."""
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(session=self.session, user=self.student)
        self.session.status = "in_progress"
        self.session.save()
        response = self.client.post(reverse("start_game", args=[self.session.pin]))
        self.assertRedirects(response, reverse("lobby", args=[self.session.pin]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "in_progress")

    # --- session_play_view (игровой процесс) ---
    def test_session_play_view_redirect_if_not_started(self):
        """Если игра ещё не началась, студент не может зайти
        на страницу прохождения, его перенаправляет в лобби."""
        self.client.force_login(self.student)
        GameParticipant.objects.create(session=self.session, user=self.student)
        response = self.client.get(reverse("session_play", args=[self.session.pin]))
        self.assertRedirects(response, reverse("join_lobby", args=[self.session.pin]))

    def test_session_play_view_get_in_progress(self):
        """GET-запрос на страницу игры во время активной сессии
        отображает текущий вопрос."""
        self.client.force_login(self.student)
        GameParticipant.objects.create(session=self.session, user=self.student)
        self.session.status = "in_progress"
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()
        response = self.client.get(reverse("session_play", args=[self.session.pin]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "session_play.html")
        self.assertEqual(response.context["question"].id, 1)  # из фикстуры

    def test_submit_answer_creates_game_answer(self):
        """POST на submit_answer создаёт запись GameAnswer и начисляет баллы.

        Ответ отправляется через fetch на отдельный JSON-эндпоинт — без
        перезагрузки страницы (единый экран игры с одним WebSocket)."""
        self.client.force_login(self.student)
        participant = GameParticipant.objects.create(
            session=self.session, user=self.student
        )
        self.session.status = "in_progress"
        self.session.current_question = 0
        self.session.current_question_started_at = timezone.now()
        self.session.save()

        # Сохраняем id участника в HTTP-сессии (это делает session_play_view).
        http_session = self.client.session
        http_session[f"lobby_participant_{self.session.pin}"] = participant.id
        http_session.save()

        data = {"answer": "1", "timed_out": "0"}
        response = self.client.post(
            reverse("submit_answer", args=[self.session.pin]), data
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        game_answer = GameAnswer.objects.filter(participant=participant).first()
        self.assertIsNotNone(game_answer)
        self.assertTrue(game_answer.is_correct)
        self.assertGreater(game_answer.points, 0)

    # --- quiz_sessions_list_view (для учителя) ---
    def test_quiz_sessions_list_view(self):
        """Учитель может просмотреть список всех сессий для своего квиза."""
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("quiz_sessions_list", args=[self.quiz.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz_sessions_list.html")
        self.assertIn("sessions", response.context)

    # --- session_results_teacher_view (детальные результаты) ---
    def test_session_results_teacher_view(self):
        """Учитель может просмотреть детальные результаты по конкретной сессии."""
        self.client.force_login(self.teacher)
        GameParticipant.objects.create(session=self.session, user=self.student, score=4)
        question = self.quiz.questions.first()
        GameAnswer.objects.create(
            session=self.session,
            participant=GameParticipant.objects.get(
                session=self.session, user=self.student
            ),
            question=question,
            is_correct=True,
            points=4,
        )
        response = self.client.get(
            reverse("session_results_teacher", args=[self.session.pin])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "session_results_teacher.html")
        self.assertIn("rows", response.context)
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0]["user"], self.student)


class PreservationPropertyTest(TestCase):
    """Тесты сохранения существующего поведения лобби (Property 2: Preservation).

    **Проверяет: Требования 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

    Эти тесты фиксируют ТЕКУЩЕЕ корректное поведение, которое должно
    остаться неизменным после применения исправлений багов.
    Все тесты должны ПРОХОДИТЬ как на неисправленном, так и на исправленном коде.
    """

    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.get(pk=2)
        self.student = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)  # active quiz

    # --- Requirement 3.1: Normal exit via "Выйти" preserves delete + redirect ---
    def test_delete_session_view_deletes_and_redirects(self):
        """Preservation: delete_session_view POST удаляет сессию и редиректит на my_quizzes.

        Требование 3.1: Хост нажимает «Выйти» — сессия удаляется, редирект на my_quizzes.
        """
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="900001",
            status=GameSession.WAITING,
            is_locked=False,
        )
        session_id = session.id

        self.client.force_login(self.teacher)
        response = self.client.post(reverse("delete_session", args=[session.pin]))

        # Should redirect to my_quizzes
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("my_quizzes"), response.url)

        # Session should be deleted
        self.assertFalse(
            GameSession.objects.filter(id=session_id).exists(),
            "Preservation violated: delete_session_view did not delete the session.",
        )

    # --- Requirement 3.2: Non-participant on IN_PROGRESS session gets error ---
    def test_join_lobby_non_participant_in_progress_gets_error(self):
        """Preservation: non-participant на IN_PROGRESS сессии получает 200 с ошибкой.

        Требование 3.2: Новый пользователь (не участник) пытается войти в
        IN_PROGRESS сессию — видит ошибку «Игра уже началась или завершена».
        """
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="900002",
            status=GameSession.IN_PROGRESS,
            is_locked=False,
            current_question=0,
            current_question_started_at=timezone.now(),
        )

        # Student is NOT a participant in this session
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[session.pin]))

        self.assertEqual(
            response.status_code,
            200,
            "Preservation violated: non-participant on IN_PROGRESS session "
            "should get 200 with error template.",
        )
        self.assertTemplateUsed(response, "lobby_error.html")
        self.assertContains(response, "Игра уже началась или завершена")

    # --- Requirement 3.3: Locked lobby blocks new players ---
    def test_join_lobby_locked_session_blocks_player(self):
        """Preservation: locked лобби блокирует новых игроков с ошибкой.

        Требование 3.3: Пользователь пытается войти в закрытое лобби —
        видит ошибку «Лобби закрыто для новых игроков».
        """
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="900003",
            status=GameSession.WAITING,
            is_locked=True,
        )

        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[session.pin]))

        self.assertEqual(
            response.status_code,
            200,
            "Preservation violated: locked lobby should return 200 with error.",
        )
        self.assertTemplateUsed(response, "lobby_error.html")
        self.assertContains(response, "Лобби закрыто для новых игроков")

    # --- Requirement 3.4: Full lobby blocks new players ---
    def test_join_lobby_full_session_blocks_player(self):
        """Preservation: полное лобби (25 игроков) блокирует новых игроков.

        Требование 3.4: Пользователь пытается войти в полное лобби —
        видит ошибку «Лобби заполнено (максимум 25 игроков)».
        """
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="900004",
            status=GameSession.WAITING,
            is_locked=False,
        )

        # Create 25 participants to fill the lobby
        for i in range(25):
            user = User.objects.create_user(
                username=f"filler_user_{i}", password="testpass"
            )
            GameParticipant.objects.create(session=session, user=user)

        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[session.pin]))

        self.assertEqual(
            response.status_code,
            200,
            "Preservation violated: full lobby should return 200 with error.",
        )
        self.assertTemplateUsed(response, "lobby_error.html")
        self.assertContains(response, "Лобби заполнено (максимум 25 игроков)")

    # --- Requirement 3.5: Normal lobby creation (no orphans) works ---
    def test_create_lobby_no_orphans_creates_session_normally(self):
        """Preservation: create_lobby_view без существующих WAITING сессий работает нормально.

        Требование 3.5: Хост создаёт лобби для квиза без осиротевших сессий —
        сессия создаётся и происходит редирект на страницу лобби.
        """
        # Use an ACTIVE quiz (fixture quiz is DRAFT by default)
        active_quiz = Quiz.objects.create(
            title="Active Quiz", creator=self.teacher, status=Quiz.ACTIVE
        )

        # Ensure no existing WAITING sessions for this teacher
        GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING
        ).delete()

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("create_lobby", args=[active_quiz.id]))

        # Should redirect to the lobby page
        self.assertEqual(
            response.status_code,
            302,
            "Preservation violated: create_lobby_view should redirect to lobby.",
        )

        # A new session should exist
        new_session = GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING, quiz=active_quiz
        ).first()
        self.assertIsNotNone(
            new_session,
            "Preservation violated: create_lobby_view did not create a new session.",
        )

        # Redirect should point to the lobby URL
        self.assertIn(
            reverse("lobby", args=[new_session.pin]),
            response.url,
            "Preservation violated: redirect target is not the lobby page.",
        )

    # --- Requirement 3.6: Player joining WAITING session gets GameParticipant ---
    def test_join_lobby_waiting_session_creates_participant(self):
        """Preservation: игрок входит в WAITING сессию — создаётся GameParticipant, ответ 200.

        Требование 3.6: Игрок входит в WAITING сессию по PIN —
        создаётся GameParticipant и рендерится join_lobby.html.
        """
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="900006",
            status=GameSession.WAITING,
            is_locked=False,
        )

        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[session.pin]))

        self.assertEqual(
            response.status_code,
            200,
            "Preservation violated: joining WAITING session should return 200.",
        )
        self.assertTemplateUsed(response, "join_lobby.html")
        self.assertTrue(
            GameParticipant.objects.filter(session=session, user=self.student).exists(),
            "Preservation violated: GameParticipant was not created for player "
            "joining a WAITING session.",
        )


class BugConditionExplorationTest(TestCase):
    """Тесты исследования баг-условий: очистка осиротевших сессий и переподключение игрока.

    **Проверяет: Требования 1.1, 1.2, 1.3**

    Эти тесты кодируют ОЖИДАЕМОЕ (правильное) поведение. Они спроектированы так,
    чтобы ПАДАТЬ на неисправленном коде, доказывая наличие багов.
    После применения исправления тесты должны проходить.
    """

    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.get(pk=2)
        self.student = User.objects.get(pk=1)
        self.quiz = Quiz.objects.get(pk=1)
        # Ensure quiz is ACTIVE so create_lobby_view doesn't early-return
        self.quiz.status = Quiz.ACTIVE
        self.quiz.save()

    def test_create_lobby_deletes_existing_waiting_session(self):
        """Случай A: Хост с существующей WAITING сессией создаёт новое лобби.

        Баг-условие (Треб. 1.2): create_lobby_view НЕ удаляет осиротевшие
        WAITING сессии при создании нового лобби для того же хоста.
        Ожидаемое поведение: старая WAITING сессия должна быть удалена.
        """
        # Create an existing WAITING session for the host
        old_session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="111111",
            status=GameSession.WAITING,
            is_locked=False,
        )
        old_session_id = old_session.id

        # Host creates a new lobby for the same quiz
        self.client.force_login(self.teacher)
        self.client.get(reverse("create_lobby", args=[self.quiz.id]))

        # Assert: the old WAITING session should no longer exist
        self.assertFalse(
            GameSession.objects.filter(id=old_session_id).exists(),
            "Bug confirmed: Old WAITING session was NOT deleted when host "
            "created a new lobby. create_lobby_view does not clean up orphans.",
        )

    def test_join_lobby_redirects_existing_participant_to_session_play(self):
        """Случай B: Существующий GameParticipant пытается войти в IN_PROGRESS сессию.

        Баг-условие (Треб. 1.3): join_lobby_view возвращает 200 с шаблоном ошибки
        вместо редиректа существующего участника на session_play.

        Ожидаемое поведение: должен быть редирект (302) на URL session_play.
        """
        # Create an IN_PROGRESS session
        session = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="222222",
            status=GameSession.IN_PROGRESS,
            is_locked=False,
            current_question=0,
            current_question_started_at=timezone.now(),
        )

        # Create a GameParticipant for the student in this session
        GameParticipant.objects.create(session=session, user=self.student)

        # Student (existing participant) tries to join via PIN
        self.client.force_login(self.student)
        response = self.client.get(reverse("join_lobby", args=[session.pin]))

        # Assert: should be a redirect (302) to session_play
        self.assertEqual(
            response.status_code,
            302,
            "Bug confirmed: join_lobby_view returns 200 with error template "
            "instead of 302 redirect for existing participant in IN_PROGRESS session.",
        )
        self.assertIn(
            reverse("session_play", args=[session.pin]),
            response.url,
            "Bug confirmed: Redirect target is not session_play URL.",
        )

    def test_create_lobby_deletes_all_orphaned_waiting_sessions(self):
        """Случай C: Хост с несколькими WAITING сессиями создаёт новое лобби.

        Баг-условие (Треб. 1.2): create_lobby_view НЕ удаляет осиротевшие
        WAITING сессии, оставляя несколько «сирот» в базе данных.

        Ожидаемое поведение: все старые WAITING сессии должны быть удалены,
        и должна остаться только новая.
        """
        # Create multiple WAITING sessions for the host
        session1 = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="333333",
            status=GameSession.WAITING,
            is_locked=False,
        )
        session2 = GameSession.objects.create(
            quiz=self.quiz,
            host=self.teacher,
            pin="444444",
            status=GameSession.WAITING,
            is_locked=False,
        )
        old_session_ids = [session1.id, session2.id]

        # Host creates a new lobby
        self.client.force_login(self.teacher)
        self.client.get(reverse("create_lobby", args=[self.quiz.id]))

        # Assert: all old WAITING sessions should be deleted
        remaining_old = GameSession.objects.filter(id__in=old_session_ids).count()
        self.assertEqual(
            remaining_old,
            0,
            "Bug confirmed: Old WAITING sessions were NOT deleted when host "
            "created a new lobby. Multiple orphans remain in the database.",
        )

        # Assert: only one WAITING session should exist for this host (the new one)
        waiting_sessions = GameSession.objects.filter(
            host=self.teacher, status=GameSession.WAITING
        )
        self.assertEqual(
            waiting_sessions.count(),
            1,
            "Bug confirmed: Expected exactly 1 WAITING session after creating "
            "new lobby, but found multiple (orphans not cleaned up).",
        )
