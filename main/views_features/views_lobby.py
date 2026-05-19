"""Views для лобби"""

import uuid
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from main.models import (
    GameSession,
    Quiz,
    GameParticipant,
    GameAnswer,
    Question,
    QuizResult,
)
from django.utils import timezone
from main.services.quiz_revisions import (
    get_current_revision,
    get_session_max_score,
    get_session_questions,
)
from main.services.quiz_scoring import score_question


def _get_request_user(request):
    """Возвращает пользователя для игры: реального или гостевого."""
    if request.user.is_authenticated:
        return request.user

    guest_user_id = request.session.get("guest_user_id")
    if guest_user_id:
        try:
            return User.objects.get(pk=guest_user_id)
        except User.DoesNotExist:
            request.session.pop("guest_user_id", None)

    username = f"guest_{uuid.uuid4().hex[:8]}"
    guest_user = User.objects.create_user(username=username)
    request.session["guest_user_id"] = guest_user.id
    return guest_user


@login_required(login_url="login_page")
def create_lobby_view(request, quiz_id):
    """Создание лобби по текущей ревизии квиза."""
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)

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
    return redirect("lobby", pin=pin)


@login_required(login_url="login_page")
@require_POST
def delete_session_view(request, pin):
    """"""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    session.delete()
    return redirect("my_quizzes")


@login_required(login_url="login_page")
def api_players_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    participants = session.participants.select_related("user").all()

    players = [
        {
            "username": p.user.username,
        }
        for p in participants
    ]

    return JsonResponse(
        {
            "players": players,
            "count": len(players),
            "is_locked": session.is_locked,
        }
    )


def join_lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    current_user = _get_request_user(request)

    # Auto-expire WAITING sessions older than 1 hour
    if session.status == GameSession.WAITING:
        expiry_threshold = timezone.now() - timezone.timedelta(hours=1)
        if session.created_at < expiry_threshold:
            session.delete()
            return render(
                request, "lobby_error.html",
                {"message": "Это лобби истекло и было закрыто."},
            )

    if session.host == current_user:
        return redirect("lobby", pin=pin)

    if session.status == GameSession.IN_PROGRESS and GameParticipant.objects.filter(
        session=session, user=current_user
    ).exists():
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

    GameParticipant.objects.get_or_create(session=session, user=current_user)

    return render(request, "join_lobby.html", {"session": session})


@login_required(login_url="login_page")
@require_POST
def start_game_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    if session.participants.count() == 0:
        return redirect("lobby", pin=pin)
    session.status = GameSession.IN_PROGRESS
    session.current_question_started_at = timezone.now()
    session.save()
    return redirect("lobby", pin=pin)


def api_state_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    return JsonResponse(
        {
            "status": session.status,
        }
    )


@login_required(login_url="login_page")
def api_game_stats_view(request, pin):
    """API: статистика игры в реальном времени для хоста."""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    questions = get_session_questions(session)
    total_questions = len(questions)
    total_participants = session.participants.count()
    answered_count = session.participants.filter(is_answered=True).count()

    current_q = min(session.current_question, total_questions - 1)
    current_question_text = ""
    if 0 <= current_q < total_questions:
        current_question_text = questions[current_q].text

    participants = (
        session.participants.select_related("user")
        .order_by("-score")
    )
    players = [
        {
            "username": p.user.username,
            "score": p.score,
            "is_answered": p.is_answered,
        }
        for p in participants
    ]

    # Build history of answers per question
    question_history = []
    for i, q in enumerate(questions):
        if i >= session.current_question and session.status != GameSession.FINISHED:
            break
        answer_lookup = {"session": session}
        if session.revision_id:
            answer_lookup["revision_question"] = q
        else:
            answer_lookup["question"] = q

        answers = GameAnswer.objects.filter(**answer_lookup).select_related(
            "participant__user"
        )
        q_data = {
            "number": i + 1,
            "text": q.text,
            "answers": [
                {
                    "username": a.participant.user.username,
                    "is_correct": a.is_correct,
                    "points": a.points,
                }
                for a in answers
            ],
        }
        question_history.append(q_data)

    return JsonResponse({
        "status": session.status,
        "current_question": min(current_q + 1, total_questions),
        "total_questions": total_questions,
        "current_question_text": current_question_text,
        "answered_count": answered_count,
        "total_participants": total_participants,
        "players": players,
        "question_history": question_history,
    })


def session_play_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    current_user = _get_request_user(request)
    participant = GameParticipant.objects.filter(
        session=session,
        user=current_user,
    ).first()
    if participant is None:
        return redirect("join_lobby", pin=pin)

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
        )
        request.session[result_session_key] = result.id

    question = questions[session.current_question]
    question_started_at = session.current_question_started_at or timezone.now()
    elapsed_seconds = int((timezone.now() - question_started_at).total_seconds())
    remaining_seconds = max(0, question.time_limit - elapsed_seconds)
    server_timed_out = remaining_seconds <= 0

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

            total_participants = session.participants.count()
            answered_count = session.participants.filter(is_answered=True).count()

            if answered_count >= total_participants:
                session.participants.update(is_answered=False)
                session.current_question += 1

                if session.current_question >= total:
                    session.status = GameSession.FINISHED
                    session.current_question_started_at = None
                else:
                    session.current_question_started_at = timezone.now()

                session.save()

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
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)
    sessions = quiz.sessions.all().order_by("-created_at")
    return render(
        request,
        "quiz_sessions_list.html",
        {
            "quiz": quiz,
            "sessions": sessions,
        },
    )


@login_required
def session_results_teacher_view(request, pin):
    """Детальные результаты сессии для учителя: таблица участник × вопрос."""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)

    questions = get_session_questions(session)
    max_score = get_session_max_score(session)

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
