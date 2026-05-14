"""Views для лобби"""

import logging
from django.contrib.auth.decorators import login_required
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

logger = logging.getLogger(__name__)


@login_required
def create_lobby_view(request, quiz_id):
    """Создание лобби по текущей ревизии квиза."""
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)

    if quiz.status == Quiz.DRAFT:
        return redirect("my_quizzes")

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


@login_required
def lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    return render(request, "lobby.html", {"session": session})


@login_required
@require_POST
def toggle_lock_view(request, pin):
    """Закрытие/открытие возможности присоединиться к сессии"""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    session.is_locked = not session.is_locked
    session.save()
    logger.info(
        "Пользователь %s %s лобби %s (PIN: %s) (IP: %s)",
        request.user.username,
        "закрыл" if session.is_locked else "открыл",
        session.quiz.title,
        pin,
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("lobby", pin=pin)


@login_required
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


@login_required
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


@login_required
def join_lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)

    if session.host == request.user:
        return redirect("lobby", pin=pin)

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

    GameParticipant.objects.get_or_create(session=session, user=request.user)

    logger.info(
        "Игрок %s присоединился к лобби %s (квиз «%s», хост: %s) (IP: %s)",
        request.user.username,
        pin,
        session.quiz.title,
        session.host.username,
        request.META.get("REMOTE_ADDR"),
    )
    return render(request, "join_lobby.html", {"session": session})


@login_required
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
    logger.info(
        "Пользователь %s начал игру в лобби %s (квиз «%s», участников: %d) (IP: %s)",
        request.user.username,
        pin,
        session.quiz.title,
        session.participants.count(),
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("lobby", pin=pin)


@login_required
def api_state_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    return JsonResponse(
        {
            "status": session.status,
        }
    )


@login_required
def session_play_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    participant = get_object_or_404(
        GameParticipant,
        session=session,
        user=request.user,
    )

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
                user=request.user,
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
            },
        )

    if session.status != GameSession.IN_PROGRESS:
        return redirect("join_lobby", pin=pin)

    result_session_key = f"lobby_result_{pin}"
    result_id = request.session.get(result_session_key)

    if result_id is None:
        result = QuizResult.objects.create(
            user=request.user,
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