"""Views для лобби"""

import logging
import uuid
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from main.models import (
    GameSession,
    Quiz,
    GameParticipant,
    GameAnswer,
    QuizResult,
)
from django.utils import timezone


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


from main.services.guest_cleanup import (
    cleanup_guest_users,
    resolve_display_name_from_user,
)
from main.services.quiz_revisions import (
    get_current_revision,
    get_session_max_score,
    get_session_questions,
)
from main.services.quiz_scoring import score_question
from main.services import realtime

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
    server_timed_out = remaining_seconds <= 0

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

    if request.method == "POST":
        answer_lookup = {
            "session": session,
            "participant": participant,
        }
        if session.revision_id:
            answer_lookup["revision_question"] = question
        else:
            answer_lookup["question"] = question

        existing_answer = GameAnswer.objects.filter(**answer_lookup).first()
        if existing_answer is not None:
            return redirect("session_play", pin=pin)

        if not participant.is_answered:
            timed_out = request.POST.get("timed_out") == "1" or server_timed_out

            score_result = score_question(
                question,
                request,
                timed_out=timed_out,
            )
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
                request.user.username,
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
                # Все ответили, но вопрос не переключаем автоматически
                # Учитель должен нажать "Следующий вопрос"
                session.ready_for_next_question = True
                session.save()

                if session.status == GameSession.FINISHED:
                    cleanup_guest_users(session)

            # Уведомляем хоста об изменении статистики (новый ответ)
            realtime.broadcast_stats_changed(pin)

        return redirect("session_play", pin=pin)

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
        },
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


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
        return JsonResponse({"success": False, "error": "Метод не разрешён"}, status=405)

    if session.status == GameSession.FINISHED:
        return JsonResponse({"success": False, "error": "Игра уже завершена"}, status=400)

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

    return JsonResponse({
        "success": True,
        "current_question": session.current_question,
    })


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