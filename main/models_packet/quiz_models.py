"""
Файл для моделей quiz
"""

# pylint: disable=no-member, too-few-public-methods

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Category(models.Model):
    """
    Категория для группировки викторин.
    """

    name = models.CharField(max_length=50, unique=True, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")

    class Meta:
        """
        Метаданные
        """

        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.name)


class Quiz(models.Model):
    """Модель quiz"""

    DRAFT = "draft"
    ACTIVE = "active"
    STATUS_CHOICES = [
        (DRAFT, "Черновик"),
        (ACTIVE, "Активен"),
    ]
    title = models.CharField(
        max_length=200,
        verbose_name="Название квиза",
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_quizzes",
        verbose_name="Создатель",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quizzes",
        verbose_name="Категория",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание",
    )
    additional_info = models.TextField(
        blank=True,
        verbose_name="Дополнительная информация",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    time_limit = models.IntegerField(
        blank=True,
        null=True,
        help_text="Ограничение по времени в минутах",
        verbose_name="Лимит времени (мин)",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=DRAFT,
        verbose_name="Статус",
    )
    current_revision = models.ForeignKey(
        "QuizRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Текущая ревизия",
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name="Удалён",
    )

    class Meta:
        """
        Метаданные
        """

        verbose_name_plural = "Quizzes"

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.title)

    def total_questions(self) -> int:
        """Возвращает количество вопросов в текущей ревизии квиза."""
        if self.current_revision_id:
            return self.current_revision.question_count
        return self.questions.count()

    def total_max_score(self) -> int:
        """Возвращает максимальный балл текущей ревизии квиза."""
        if self.current_revision_id:
            return self.current_revision.max_score

        total = 0
        for question in self.questions.all():
            if question.question_type != Question.TEXT:
                total += 4 * question.coefficient
        return total


class QuizRevision(models.Model):
    """Неизменяемая ревизия квиза."""

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="revisions",
        verbose_name="Квиз",
    )
    version = models.PositiveIntegerField(verbose_name="Версия")
    title = models.CharField(max_length=200, verbose_name="Название ревизии")
    question_count = models.PositiveIntegerField(
        default=0, verbose_name="Количество вопросов"
    )
    max_score = models.PositiveIntegerField(default=0, verbose_name="Максимальный балл")
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version"]
        unique_together = ["quiz", "version"]
        verbose_name = "Ревизия квиза"
        verbose_name_plural = "Ревизии квиза"

    def __str__(self):
        return f"{self.quiz.title} v{self.version}"


class QuizReport(models.Model):
    """Жалоба пользователя на конкретную версию квиза."""

    WRONG_ANSWERS = "wrong_answers"
    INAPPROPRIATE = "inappropriate"
    OFFTOPIC = "offtopic"
    TECHNICAL_PROBLEM = "technical_problem"
    OTHER = "other"
    REASON_CHOICES = [
        (WRONG_ANSWERS, "Ошибка в вопросе или ответе"),
        (INAPPROPRIATE, "Некорректный контент"),
        (OFFTOPIC, "Не относится к теме"),
        (TECHNICAL_PROBLEM, "Техническая проблема"),
        (OTHER, "Другое"),
    ]

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "Новая"),
        (ACCEPTED, "Подтверждена"),
        (REJECTED, "Отклонена"),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name="Квиз",
    )
    revision = models.ForeignKey(
        QuizRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        verbose_name="Версия квиза",
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quiz_reports",
        verbose_name="Автор жалобы",
    )
    reason = models.CharField(
        max_length=32,
        choices=REASON_CHOICES,
        verbose_name="Причина",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=PENDING,
        verbose_name="Статус",
    )
    admin_comment = models.TextField(
        blank=True,
        verbose_name="Комментарий администратора",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_quiz_reports",
        verbose_name="Проверил",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Метаданные жалоб."""

        ordering = ["-created_at"]
        verbose_name = "Жалоба на квиз"
        verbose_name_plural = "Жалобы на квизы"
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "reporter"],
                condition=models.Q(status="pending"),
                name="unique_pending_quiz_report_per_user",
            ),
        ]

    def clean(self):
        """Проверяет обязательный комментарий для причины 'Другое'."""
        super().clean()
        if self.reason == self.OTHER and not self.comment.strip():
            raise ValidationError(
                {"comment": "Для причины «Другое» нужно описать проблему."}
            )

    def __str__(self):
        return f"Жалоба на {self.quiz} от {self.reporter}"


class Question(models.Model):
    """
    Модель вопроса
    """

    SINGLE = "single"
    MULTIPLE = "multiple"
    TEXT = "text"
    NUMBER = "number"
    QUESTION_TYPE_CHOICES = [
        (SINGLE, "Одиночный выбор"),
        (MULTIPLE, "Множественный выбор"),
        (TEXT, "Текстовый"),
        (NUMBER, "Числовой"),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField(verbose_name="Текст вопроса")
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPE_CHOICES,
        default=SINGLE,
        verbose_name="Тип вопроса",
    )
    correct_number = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Правильное число",
    )
    coefficient = models.PositiveIntegerField(
        default=1,
        verbose_name="Коэффициент",
    )
    time_limit = models.IntegerField(default=30, verbose_name="Время на ответ (сек)")
    order = models.IntegerField(default=0)

    class Meta:
        """
        Метаданные
        """

        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        ordering = ["order"]

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.text)


class RevisionQuestion(models.Model):
    """Вопрос внутри конкретной ревизии квиза."""

    revision = models.ForeignKey(
        QuizRevision,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Ревизия",
    )
    text = models.TextField(verbose_name="Текст вопроса")
    question_type = models.CharField(
        max_length=10,
        choices=Question.QUESTION_TYPE_CHOICES,
        default=Question.SINGLE,
        verbose_name="Тип вопроса",
    )
    correct_number = models.FloatField(
        null=True, blank=True, verbose_name="Правильное число"
    )
    coefficient = models.PositiveIntegerField(default=1, verbose_name="Коэффициент")
    time_limit = models.IntegerField(default=30, verbose_name="Время на ответ (сек)")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Вопрос ревизии"
        verbose_name_plural = "Вопросы ревизии"

    def __str__(self):
        return self.text


class Answer(models.Model):
    """
    Модель ответа
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    text = models.CharField(
        max_length=255,
        verbose_name="Текст ответа",
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name="Правильный",
    )

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.text)


class RevisionAnswer(models.Model):
    """Ответ для вопроса ревизии."""

    question = models.ForeignKey(
        RevisionQuestion,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Вопрос ревизии",
    )
    text = models.CharField(max_length=255, verbose_name="Текст ответа")
    is_correct = models.BooleanField(default=False, verbose_name="Правильный")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Ответ ревизии"
        verbose_name_plural = "Ответы ревизии"

    def __str__(self):
        return self.text


class QuizResult(models.Model):
    """
    Модель результата прохождения quiz
    """

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quiz_results",
    )
    display_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Отображаемое имя",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="results",
    )
    revision = models.ForeignKey(
        "QuizRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="results",
        verbose_name="Ревизия квиза",
    )
    score = models.IntegerField(default=0)
    max_score = models.IntegerField(default=0)
    score_percent = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        """
        Метаданные
        """

        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"
        ordering = ["order"]

    def __str__(self):
        return str(self.score)

    def get_display_name(self) -> str:
        """Resolve display name with fallback chain."""
        if self.display_name:
            return self.display_name
        if self.user is not None:
            return self.user.username
        return "Удалённый пользователь"
