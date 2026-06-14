"""
Файл для моделей игровых сессий
"""

import random
import string
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from .quiz_models import Quiz, Question, Answer, QuizResult
import logging

logger = logging.getLogger(__name__)


def generate_pin():
    """
    Генератор случайного ключа сессии
    """
    return "".join(random.choices(string.digits, k=6))


class GameSession(models.Model):
    """
    Класс сессии
    """

    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    STATUS_CHOICES = [
        (WAITING, "Ожидание"),
        (IN_PROGRESS, "Идёт игра"),
        (FINISHED, "Завершена"),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="Квиз",
    )
    host = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="hosted_sessions",
        verbose_name="Хост",
    )
    pin = models.CharField(
        max_length=6,
        unique=True,
        default=generate_pin,
        verbose_name="PIN-код",
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=WAITING,
        verbose_name="Статус",
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Лобби закрыто",
    )
    current_question = models.IntegerField(
        default=0,
        verbose_name="Текущий вопрос",
    )
    current_question_started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время старта текущего вопроса",
    )
    revision = models.ForeignKey(
        "QuizRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Ревизия квиза",
    )
    ready_for_next_question = models.BooleanField(
        default=False,
        verbose_name="Все ответили, готово к переключению",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        """
        Отладочная информация
        """
        return f"{self.quiz} [{self.pin}]"

class GameParticipant(models.Model):
    """
    Игра ??
    """

    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Сессия",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_participations",
        verbose_name="Игрок",
    )
    display_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Отображаемое имя",
    )
    score = models.IntegerField(default=0, verbose_name="Счёт")
    is_answered = models.BooleanField(
        default=False,
        verbose_name="Ответил на текущий вопрос",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Метаданные
        """

        ordering = ["-score"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_participant_per_session",
            ),
        ]

    def __str__(self):
        """
        Отладочная информация
        """
        return f"присоединился: {self.joined_at}"

    def get_display_name(self) -> str:
        """Resolve display name with fallback chain."""
        if self.display_name:
            return self.display_name
        if self.user is not None:
            return self.user.username
        return "Удалённый пользователь"


class GameAnswer(models.Model):
    """
    Ответы игры
    """

    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name="game_answers",
        verbose_name="Сессия",
    )
    participant = models.ForeignKey(
        GameParticipant,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Участник",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_answers",
        verbose_name="Старый вопрос",
    )
    revision_question = models.ForeignKey(
        "RevisionQuestion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_answers",
        verbose_name="Вопрос ревизии",
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Выбранный ответ",
    )
    is_correct = models.BooleanField(default=False, verbose_name="Верно")
    points = models.IntegerField(default=0, verbose_name="Баллы")
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """
        Метаданные
        """

        constraints = [
            models.UniqueConstraint(
                fields=["participant", "question"],
                condition=models.Q(question__isnull=False),
                name="unique_gameanswer_legacy_question",
            ),
            models.UniqueConstraint(
                fields=["participant", "revision_question"],
                condition=models.Q(revision_question__isnull=False),
                name="unique_gameanswer_revision_question",
            ),
        ]

    def __str__(self):
        """
        Отладочная информация
        """
        return f"{self.answer} — {self.question}"


@receiver(post_save, sender=Quiz)
def log_quiz_save(sender, instance, created, **kwargs):
    """Логирует создание и обновление квизов"""
    if created:
        logger.info(
            f"[DB CREATE] Квиз: '{instance.title}'"
            f" (ID: {instance.id}) создан пользователем {instance.creator.username}"
        )
    else:
        logger.debug(
            f"[DB UPDATE] Квиз: '{instance.title}' (ID: {instance.id}) обновлён"
        )


@receiver(post_delete, sender=Quiz)
def log_quiz_delete(sender, instance, **kwargs):
    """Логирует удаление квизов"""
    logger.warning(f"[DB DELETE] Квиз: '{instance.title}' (ID: {instance.id}) удалён")


@receiver(post_save, sender=GameSession)
def log_gamesession_save(sender, instance, created, **kwargs):
    """Логирует создание и изменение игровых сессий"""
    if created:
        logger.info(
            f"[GAME LOBBY] Создана сессия PIN: {instance.pin} для квиза '{instance.quiz.title}'"
            f" (хост: {instance.host.username})"
        )
    elif instance.status == "in_progress":
        logger.info(f"[GAME LOBBY] Сессия {instance.pin}: игра начата")
    elif instance.status == "finished":
        logger.info(f"[GAME LOBBY] Сессия {instance.pin}: игра завершена")


@receiver(post_save, sender=GameParticipant)
def log_participant_join(sender, instance, created, **kwargs):
    """Логирует подключение игроков к лобби"""
    if created:
        logger.info(
            f"[GAME JOIN] Игрок {instance.user.username} присоединился к сессии "
            f"{instance.session.pin}"
        )


@receiver(post_save, sender=QuizResult)
def log_quiz_result(sender, instance, created, **kwargs):
    """Логирует завершение квизов"""
    if not created and instance.completed:
        logger.info(
            f"[QUIZ COMPLETE] Пользователь {instance.user.username} завершил квиз '{instance.quiz.title}':"
            f" {instance.score}/{instance.max_score} ({instance.score_percent:.1f}%)"
        )
