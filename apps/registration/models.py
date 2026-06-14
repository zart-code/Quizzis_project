"""
Файл моделей профиля
"""


from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.
class Profile(models.Model):
    """Профиль пользователя"""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    ROLE_CHOICES = [
        (ADMIN, "Админ"),
        (TEACHER, "Учитель"),
        (STUDENT, "Ученик"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=STUDENT,
        verbose_name="Роль",
    )
    is_admin = models.BooleanField(default=False, verbose_name="Администратор")
    is_banned = models.BooleanField(default=False, verbose_name="Заблокирован")

    def __str__(self):
        """Отладочная информация"""
        return f"Профиль {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Создание профиля юзера"""
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance)
        if instance.username == "admin":
            profile.role = Profile.ADMIN
            profile.is_admin = True
        profile.save()


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохранить профиль"""
    if hasattr(instance, "profile"):
        profile = instance.profile
        if instance.username == "admin":
            profile.role = Profile.ADMIN
            profile.is_admin = True
        elif profile.role == Profile.ADMIN and not profile.is_admin:
            profile.role = Profile.TEACHER
        elif profile.is_admin and profile.role != Profile.ADMIN:
            profile.role = Profile.ADMIN
        profile.save()
