"""
Сервис очистки гостевых пользователей.

Содержит утилиты для определения отображаемого имени участника
и удаления временных гостевых аккаунтов после завершения игровой сессии.
"""

from django.contrib.auth.models import User

from apps.quiz.models import GameSession, GameParticipant


def resolve_display_name_from_user(user: User) -> str:
    """Определяет отображаемое имя на основе first_name или username пользователя.

    Возвращает first_name (без пробелов по краям), если оно непустое,
    иначе возвращает username.
    """
    if user.first_name and user.first_name.strip():
        return user.first_name.strip()
    return user.username


def cleanup_guest_users(session: GameSession) -> int:
    """Удаляет гостевых пользователей завершённой сессии, не участвующих в других активных сессиях.

    Проверяет каждого участника с username, начинающимся на «guest_».
    Если гость не участвует в других сессиях со статусом WAITING или IN_PROGRESS,
    его учётная запись удаляется (SET_NULL каскадно обнуляет FK).

    Возвращает количество удалённых пользователей.
    """
    guest_participants = session.participants.filter(
        user__isnull=False,
        user__username__startswith="guest_",
    ).select_related("user")

    deleted_count = 0
    for participant in guest_participants:
        guest_user = participant.user
        has_active_sessions = (
            GameParticipant.objects.filter(
                user=guest_user,
                session__status__in=[GameSession.WAITING, GameSession.IN_PROGRESS],
            )
            .exclude(session=session)
            .exists()
        )

        if not has_active_sessions:
            guest_user.delete()
            deleted_count += 1

    return deleted_count
