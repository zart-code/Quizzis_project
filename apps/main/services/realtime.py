"""Real-time слой: построение payload'ов и рассылка событий через Channels.

Здесь собрана вся логика, которая раньше отдавалась по HTTP-polling
(`api_players`, `api_state`, `api_game_stats`, `api_check_kicked`,
`get_current_question`, а также `api_admin_stats/users/quizzes`). Теперь
данные считаются один раз и доставляются клиентам push-уведомлением по
WebSocket.

Функции `build_*` — синхронные, работают с ORM и вызываются как из
HTTP-view, так и из WebSocket-consumer'а (через database_sync_to_async).
Функции `broadcast_*` публикуют событие в группу канала.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.quiz.models import GameSession, GameAnswer
from apps.main.services.quiz_revisions import (
    get_session_questions,
)


# ---------------------------------------------------------------------------
# Имена групп
# ---------------------------------------------------------------------------
def lobby_group(pin: str) -> str:
    """Группа всех участников лобби/сессии (игроки + хост)."""
    return f"lobby_{pin}"


ADMIN_GROUP = "admin_panel"


# ---------------------------------------------------------------------------
# Построение payload'ов (синхронно, ORM)
# ---------------------------------------------------------------------------
def build_player_list(session: GameSession) -> dict:
    """Список игроков для экрана ожидания хоста."""
    participants = session.participants.select_related("user").all()
    players = [
        {"id": p.id, "username": p.get_display_name()}
        for p in participants
    ]
    return {
        "players": players,
        "count": len(players),
        "is_locked": session.is_locked,
        "status": session.status,
    }


def build_game_stats(session: GameSession) -> dict:
    """Полная статистика игры в реальном времени для хоста."""
    questions = get_session_questions(session)
    total_questions = len(questions)
    total_participants = session.participants.count()
    answered_count = session.participants.filter(is_answered=True).count()

    current_q = min(session.current_question, total_questions - 1)
    current_question_text = ""
    if 0 <= current_q < total_questions:
        current_question_text = questions[current_q].text

    participants = session.participants.select_related("user").order_by("-score")
    players = [
        {
            "username": p.get_display_name(),
            "score": p.score,
            "is_answered": p.is_answered,
        }
        for p in participants
    ]

    # История ответов по уже завершённым вопросам.
    question_history = []
    for i, q in enumerate(questions):
        if i > session.current_question:
            break
        if (
            i == session.current_question
            and session.status != GameSession.FINISHED
            and not session.ready_for_next_question
        ):
            break

        answer_lookup = {"session": session}
        if session.revision_id:
            answer_lookup["revision_question"] = q
        else:
            answer_lookup["question"] = q

        answers = GameAnswer.objects.filter(**answer_lookup).select_related(
            "participant__user"
        )
        question_history.append(
            {
                "number": i + 1,
                "text": q.text,
                "answers": [
                    {
                        "username": a.participant.get_display_name(),
                        "is_correct": a.is_correct,
                        "points": a.points,
                    }
                    for a in answers
                ],
            }
        )

    current_options = []
    if 0 <= current_q < total_questions:
        current_options = [
            {"id": ao.id, "text": ao.text}
            for ao in questions[current_q].answers.all()
        ]

    time_remaining = 0
    if session.current_question_started_at and 0 <= current_q < total_questions:
        elapsed = int(
            (timezone.now() - session.current_question_started_at).total_seconds()
        )
        time_remaining = max(0, questions[current_q].time_limit - elapsed)

    return {
        "status": session.status,
        "current_question": min(current_q + 1, total_questions),
        "total_questions": total_questions,
        "current_question_text": current_question_text,
        "answered_count": answered_count,
        "total_participants": total_participants,
        "players": players,
        "question_history": question_history,
        "current_options": current_options,
        "ready_for_next_question": session.ready_for_next_question,
        "time_remaining": time_remaining,
    }


def build_player_state(session: GameSession, participant_id: int | None) -> dict:
    """Состояние сессии глазами игрока (для единого экрана игры).

    `kicked` — участника больше нет в лобби (его выгнали или сессию
    пересоздали). `has_answered` — есть ли реальный ответ игрока на
    текущий вопрос. `question` — данные текущего вопроса, чтобы игрок
    мог отрисовать его без перезагрузки страницы.
    """
    kicked = True
    has_answered = False
    score = 0
    question_payload = None
    time_remaining = 0

    questions = get_session_questions(session)
    total_questions = len(questions)
    idx = session.current_question

    participant = None
    if participant_id:
        participant = session.participants.filter(id=participant_id).first()

    if participant is not None:
        kicked = False
        score = participant.score
        if 0 <= idx < total_questions:
            current_question = questions[idx]
            answer_check = {"session": session, "participant": participant}
            if session.revision_id:
                answer_check["revision_question"] = current_question
            else:
                answer_check["question"] = current_question
            has_answered = GameAnswer.objects.filter(**answer_check).exists()

    # Данные текущего вопроса (только если игра идёт и вопрос существует).
    if (
        session.status == GameSession.IN_PROGRESS
        and 0 <= idx < total_questions
    ):
        q = questions[idx]
        question_payload = {
            "index": idx,
            "number": idx + 1,
            "text": q.text,
            "type": q.question_type,
            "time_limit": q.time_limit,
            "options": [
                {"id": a.id, "text": a.text} for a in q.answers.all()
            ],
        }
        if session.current_question_started_at:
            elapsed = int(
                (timezone.now() - session.current_question_started_at).total_seconds()
            )
            time_remaining = max(0, q.time_limit - elapsed)
        else:
            time_remaining = q.time_limit

    return {
        "status": session.status,
        "current_question": session.current_question,
        "total_questions": total_questions,
        "kicked": kicked,
        "has_answered": has_answered,
        "score": score,
        "question": question_payload,
        "time_remaining": time_remaining,
    }


# ---------------------------------------------------------------------------
# Рассылка событий (вызывается из HTTP-views, синхронный контекст)
# ---------------------------------------------------------------------------
def _send(pin: str, message: dict) -> None:
    """Отправить служебное сообщение в группу лобби.

    Безопасно: если channel layer недоступен, ошибка проглатывается, чтобы
    не ломать основной HTTP-flow.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(lobby_group(pin), message)
    except Exception:  # noqa: BLE001 - real-time не должен ронять запрос
        pass


def broadcast_lobby_changed(pin: str) -> None:
    """Состав лобби или его блокировка изменились (для экрана ожидания хоста)."""
    _send(pin, {"type": "lobby_changed"})


def broadcast_player_kicked(pin: str, participant_id: int) -> None:
    """Игрок выгнан: уведомляем хоста (обновить список) и самого игрока."""
    _send(pin, {"type": "player_kicked", "participant_id": participant_id})


def broadcast_game_started(pin: str) -> None:
    """Игра началась: игроки переходят на экран игры, хост — на дашборд."""
    _send(pin, {"type": "game_started"})


def broadcast_question_advanced(pin: str) -> None:
    """Учитель переключил вопрос (или игра завершена)."""
    _send(pin, {"type": "question_advanced"})


def broadcast_stats_changed(pin: str) -> None:
    """Игрок ответил / изменилась статистика — обновить дашборд хоста."""
    _send(pin, {"type": "stats_changed"})


# ---------------------------------------------------------------------------
# Админ-панель: построение payload'ов и рассылка
# ---------------------------------------------------------------------------
def build_admin_stats() -> dict:
    """Сводная статистика для карточек админ-панели."""
    from django.contrib.auth.models import User

    from apps.quiz_game.models import QuizReport
    from apps.quiz_game.models import Quiz
    from apps.registration import Profile

    return {
        "total_users": User.objects.count(),
        "total_quizzes": Quiz.objects.filter(is_deleted=False).count(),
        "total_admins": Profile.objects.filter(role=Profile.ADMIN).count(),
        "total_banned_users": Profile.objects.filter(is_banned=True).count(),
        "total_pending_reports": QuizReport.objects.filter(
            status=QuizReport.PENDING,
            quiz__is_deleted=False,
        ).count(),
    }


def build_admin_users() -> list:
    """Список пользователей для таблицы админ-панели."""
    from django.contrib.auth.models import User
    from django.db.models import Count

    users = (
        User.objects.annotate(quiz_count=Count("created_quizzes"))
        .select_related("profile")
        .order_by("id")
        .values(
            "id",
            "username",
            "email",
            "date_joined",
            "quiz_count",
            "profile__role",
            "profile__is_banned",
        )
    )
    # date_joined -> str для JSON-сериализации.
    result = []
    for u in users:
        item = dict(u)
        if item.get("date_joined") is not None:
            item["date_joined"] = item["date_joined"].isoformat()
        result.append(item)
    return result


def build_admin_quizzes() -> list:
    """Список квизов для таблицы админ-панели."""
    from django.db.models import Case, Count, F, IntegerField, When

    from apps.quiz_game.models import Quiz

    quizzes = (
        Quiz.objects.filter(is_deleted=False)
        .select_related("creator")
        .annotate(
            question_count=Case(
                When(
                    current_revision__isnull=False,
                    then=F("current_revision__question_count"),
                ),
                default=Count("questions"),
                output_field=IntegerField(),
            )
        )
        .order_by("-created_at")
        .values(
            "id",
            "title",
            "status",
            "created_at",
            "question_count",
            "creator__id",
            "creator__username",
        )
    )
    result = []
    for q in quizzes:
        item = dict(q)
        if item.get("created_at") is not None:
            item["created_at"] = item["created_at"].isoformat()
        result.append(item)
    return result


def build_admin_snapshot() -> dict:
    """Полный снимок состояния админ-панели (для push и для sync)."""
    return {
        "type": "admin_update",
        "stats": build_admin_stats(),
        "users": build_admin_users(),
        "quizzes": build_admin_quizzes(),
    }


def broadcast_admin_update() -> None:
    """Уведомить все открытые админ-панели об изменении данных.

    Вызывается из любых view, меняющих пользователей/квизы/жалобы.
    Сам снимок строится на стороне consumer'а (в его потоке с ORM),
    поэтому здесь шлём только сигнал.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            ADMIN_GROUP, {"type": "admin_changed"}
        )
    except Exception:  # noqa: BLE001
        pass
