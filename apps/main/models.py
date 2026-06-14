"""
Файл для моделей database. А где модели?
Так стоп, это уже было...

14.06.2026 шутка перестала быть актуальной так как произошёл рефакторинг
"""

"""
Файл для моделей достижений
"""


from django.contrib.auth.models import User
from django.db import models


class Achievement(models.Model):
    """
    Модель достижений
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, default="🏆")

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
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="user_achievements",
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Методанные
        """

        unique_together = ["user", "achievement"]
        ordering = ["-unlocked_at"]

    def __str__(self):
        """
        Отладочная информация
        """
        return f"{self.achievement.name} {self.unlocked_at}"

