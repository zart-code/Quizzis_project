from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    """
    Расширенная модель пользователя.
    """
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Аватар'
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
        verbose_name='О себе'
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        verbose_name='Дата рождения'
    )
    total_points = models.IntegerField(
        default=0,
        verbose_name='Всего баллов'
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Achievement(models.Model):
    """
    Модель достижения.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название'
    )
    description = models.TextField(
        verbose_name='Описание'
    )
    icon = models.ImageField(
        upload_to='achievements/icons/',
        blank=True,
        null=True,
        verbose_name='Иконка'
    )
    points = models.PositiveIntegerField(
        default=0,
        verbose_name='Баллы за достижение'
    )
    condition = models.TextField(
        blank=True,
        help_text='Условие получения достижения (опционально)',
        verbose_name='Условие'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
        # default=timezone.now
    )

    class Meta:
        verbose_name = 'Достижение'
        verbose_name_plural = 'Достижения'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    """
    Связь пользователя и достижения (многие ко многим с датой получения).
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='achievements',
        verbose_name='Пользователь'
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='users',
        verbose_name='Достижение'
    )
    earned_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата получения'
    )

    class Meta:
        verbose_name = 'Достижение пользователя'
        verbose_name_plural = 'Достижения пользователей'
        unique_together = ('user', 'achievement')  # предотвращает повторное получение

    def __str__(self):
        return f'{self.user.username} - {self.achievement.name}'


class Category(models.Model):
    """
    Категория для группировки викторин.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Название'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Quizz(models.Model):
    """
    Модель викторины.
    """
    title = models.CharField(
        max_length=200,
        verbose_name='Название'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quizzes',
        verbose_name='Категория'
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_quizzes',
        verbose_name='Автор'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    is_published = models.BooleanField(
        default=False,
        verbose_name='Опубликовано'
    )
    time_limit = models.DurationField(
        blank=True,
        null=True,
        help_text='Общее время на прохождение (например, 00:30:00 для 30 минут)',
        verbose_name='Лимит времени'
    )
    pass_score = models.PositiveIntegerField(
        default=0,
        help_text='Минимальное количество баллов для зачета',
        verbose_name='Проходной балл'
    )

    class Meta:
        verbose_name = 'Викторина'
        verbose_name_plural = 'Викторины'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def total_questions(self):
        """Возвращает количество вопросов в викторине."""
        return self.questions.count()


class Question(models.Model):
    """
    Модель вопроса в викторине.
    """
    class QuestionType(models.TextChoices):
        SINGLE = 'single', 'Одиночный выбор'
        MULTIPLE = 'multiple', 'Множественный выбор'
        TEXT = 'text', 'Текстовый ответ'

    quizz = models.ForeignKey(
        Quizz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Викторина'
    )
    text = models.TextField(
        verbose_name='Текст вопроса'
    )
    question_type = models.CharField(
        max_length=10,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE,
        verbose_name='Тип вопроса'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядковый номер'
    )
    points = models.PositiveIntegerField(
        default=1,
        verbose_name='Баллы за правильный ответ'
    )
    image = models.ImageField(
        upload_to='questions/',
        blank=True,
        null=True,
        verbose_name='Изображение'
    )

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['order']

    def __str__(self):
        return f'{self.quizz.title} - Вопрос {self.order}'

class Answer(models.Model):
    """
    Вариант ответа на вопрос.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос'
    )
    text = models.CharField(
        max_length=255,
        verbose_name='Текст ответа'
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name='Правильный?'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок'
    )

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['order']

    def __str__(self):
        return self.text