"""
Файл для моделей database
"""
import random
import string
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Профиль пользователя"""
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'
    ROLE_CHOICES = [
        (ADMIN, 'Админ'),
        (TEACHER, 'Учитель'),
        (STUDENT, 'Ученик'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=STUDENT,
        verbose_name='Роль',
    )
    is_admin = models.BooleanField(default=False, verbose_name='Администратор')
    is_banned = models.BooleanField(default=False, verbose_name='Заблокирован')

    def __str__(self):
        """Отладочная информация"""
        return f'Профиль {self.user.username}'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Создание профиля юзера"""
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance)
        if instance.username == 'admin':
            profile.role = Profile.ADMIN
            profile.is_admin = True
        profile.save()


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохранить профиль"""
    if hasattr(instance, 'profile'):
        profile = instance.profile
        if instance.username == 'admin':
            profile.role = Profile.ADMIN
            profile.is_admin = True
        elif profile.role == Profile.ADMIN and not profile.is_admin:
            profile.role = Profile.TEACHER
        elif profile.is_admin and profile.role != Profile.ADMIN:
            profile.role = Profile.ADMIN
        profile.save()


def generate_pin():
    """
    Генератор случайного ключа сессии
    """
    return ''.join(random.choices(string.digits, k=6))


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
        """
        Метаданные
        """
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.name)


class Quiz(models.Model):
    """ Модель quiz """

    DRAFT = 'draft'
    ACTIVE = 'active'
    STATUS_CHOICES = [
        (DRAFT, 'Черновик'),
        (ACTIVE, 'Активен'),
    ]
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
    created_at = models.DateTimeField(auto_now_add=True)
    time_limit = models.IntegerField(
        blank=True,
        null=True,
        help_text='Ограничение по времени в минутах',
        verbose_name='Лимит времени (мин)',
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=DRAFT,
        verbose_name='Статус',
    )

    class Meta:
        """
        Метаданные
        """
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.title)

    def total_questions(self) -> object:
        """Возвращает количество вопросов в викторине."""
        return self.questions.count()


class Question(models.Model):
    """
    Модель вопроса
    """
    SINGLE = 'single'
    MULTIPLE = 'multiple'
    TEXT = 'text'
    NUMBER = 'number'
    QUESTION_TYPE_CHOICES = [
        (SINGLE, 'Одиночный выбор'),
        (MULTIPLE, 'Множественный выбор'),
        (TEXT, 'Текстовый'),
        (NUMBER, 'Числовой'),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField(verbose_name='Текст вопроса')
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPE_CHOICES,
        default=SINGLE,
        verbose_name='Тип вопроса',
    )
    correct_number = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Правильное число',
    )
    coefficient = models.PositiveIntegerField(
        default=1,
        verbose_name='Коэффициент',
    )
    time_limit = models.IntegerField(default=30, verbose_name='Время на ответ (сек)')
    order = models.IntegerField(default=0)

    class Meta:
        """
        Метаданные
        """
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['order']

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.text)


class Answer(models.Model):
    """
    Модель ответа
    """
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
        """
        Отладочная информация
        """
        return str(self.text)


class QuizResult(models.Model):
    """
    Модель результата прохождения quiz
    """
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

    order = models.PositiveIntegerField(default=0)

    class Meta:
        """
        Метаданные
        """
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['order']

    def __str__(self):
        return str(self.score)


class Achievement(models.Model):
    """
    Модель достижений
    """
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, default='🏆')

    def __str__(self):
        """
        Отладочная информация
        """
        return str(self.name)


class UserAchievement(models.Model):
    """
    Модель достижений пользователя
    """
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
        """
        Методанные
        """
        unique_together = ['user', 'achievement']
        ordering = ['-unlocked_at']

    def __str__(self):
        """
        Отладочная информация
        """
        return f'{self.achievement.name} {self.unlocked_at}'


class GameSession(models.Model):
    """
    Класс сессии
    """
    WAITING = 'waiting'
    IN_PROGRESS = 'in_progress'
    FINISHED = 'finished'
    STATUS_CHOICES = [
        (WAITING, 'Ожидание'),
        (IN_PROGRESS, 'Идёт игра'),
        (FINISHED, 'Завершена'),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='Квиз',
    )
    host = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hosted_sessions',
        verbose_name='Хост',
    )
    pin = models.CharField(
        max_length=6,
        unique=True,
        default=generate_pin,
        verbose_name='PIN-код',
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=WAITING,
        verbose_name='Статус',
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name='Лобби закрыто',
    )
    current_question = models.IntegerField(
        default=0,
        verbose_name='Текущий вопрос',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        """
        Отладочная информация
        """
        return f'{self.quiz} [{self.pin}]'


class GameParticipant(models.Model):
    """
    Игра ??
    """
    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name='Сессия',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='game_participations',
        verbose_name='Игрок',
    )
    score = models.IntegerField(default=0, verbose_name='Счёт')
    is_answered = models.BooleanField(
        default=False,
        verbose_name='Ответил на текущий вопрос',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Метаданные
        """
        unique_together = ['session', 'user']
        ordering = ['-score']

    def __str__(self):
        """
        Отладочная информация
        """
        return f'присоединился: {self.joined_at}'


class GameAnswer(models.Model):
    """
    Ответы игры
    """
    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name='game_answers',
        verbose_name='Сессия',
    )
    participant = models.ForeignKey(
        GameParticipant,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Участник',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='game_answers',
        verbose_name='Вопрос',
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Выбранный ответ',
    )
    is_correct = models.BooleanField(default=False, verbose_name='Верно')
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """
        Метаданные
        """
        unique_together = ['participant', 'question']

    def __str__(self):
        """
        Отладочная информация
        """
        return f'{self.answer} — {self.question}'
