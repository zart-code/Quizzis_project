"""Сигналы, которые обновляют админ-панель в реальном времени.

Любое изменение пользователей, профилей, квизов или жалоб автоматически
рассылает событие в WebSocket-группу админ-панели. Так админ видит
изменения мгновенно, даже если их сделал обычный пользователь
(например, создал квиз или зарегистрировался) — без перезагрузки страницы
и без поллинга.

Используем transaction.on_commit, чтобы событие уходило только после
фактического коммита в базу: к моменту, когда consumer построит свежий
снимок, данные уже гарантированно записаны.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.quiz.models import Quiz, QuizReport
from apps.registration.models import Profile
from apps.main.services import realtime


def _schedule_admin_update() -> None:
    """Отправить обновление админ-панели после коммита транзакции."""
    transaction.on_commit(realtime.broadcast_admin_update)


@receiver(post_save, sender=Quiz)
@receiver(post_delete, sender=Quiz)
def quiz_changed(sender, **kwargs):
    """Создание/изменение/удаление квиза → обновить админку."""
    _schedule_admin_update()


@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def user_changed(sender, **kwargs):
    """Регистрация/изменение/удаление пользователя → обновить админку."""
    _schedule_admin_update()


@receiver(post_save, sender=Profile)
@receiver(post_delete, sender=Profile)
def profile_changed(sender, **kwargs):
    """Смена роли/бан/разбан → обновить админку."""
    _schedule_admin_update()


@receiver(post_save, sender=QuizReport)
@receiver(post_delete, sender=QuizReport)
def report_changed(sender, **kwargs):
    """Новая жалоба или её разбор → обновить админку."""
    _schedule_admin_update()
