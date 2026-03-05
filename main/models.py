from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Quiz(models.Model):
    title = models.CharField(
        max_length=200,
        verbose_name='Название квиза',
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_quizzes',
        verbose_name='Создатель',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quizzes',
        verbose_name='Категория',
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
    )
    additional_info = models.TextField(
        blank=True,
        verbose_name='Дополнительная информация',
    )
    is_published = models.BooleanField(
        default=False,
        verbose_name='Опубликован',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    time_limit = models.IntegerField(
        blank=True,
        null=True,
        help_text='Ограничение по времени в минутах',
        verbose_name='Лимит времени (мин)',
    )

    class Meta:
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        return self.title


class Question(models.Model):
    SINGLE = 'single'
    MULTIPLE = 'multiple'
    QUESTION_TYPE_CHOICES = [
        (SINGLE, 'Одиночный выбор'),
        (MULTIPLE, 'Множественный выбор'),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    text = models.TextField(verbose_name='Текст вопроса')
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPE_CHOICES,
        default=SINGLE,
        verbose_name='Тип вопроса',
    )
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    text = models.CharField(
        max_length=255,
        verbose_name='Текст ответа',
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name='Правильный',
    )

    def __str__(self):
        return self.text


class QuizResult(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_results',
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='results',
    )
    score = models.IntegerField(default=0)
    max_score = models.IntegerField(default=0)
    score_percent = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-completed_at', '-started_at']

    def __str__(self):
        return f'{self.user.username} - {self.quiz.title}'


class Achievement(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, default='🏆')

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='achievements',
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='user_achievements',
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-unlocked_at']

    def __str__(self):
        return f'{self.user.username} - {self.achievement.name}'
