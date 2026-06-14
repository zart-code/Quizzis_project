"""Главное приложение"""

from django.apps import AppConfig


class MainConfig(AppConfig):
    """Настройки приложения"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "main"

    def ready(self):
        """Подключаем сигналы при старте приложения."""
        # Импорт регистрирует получателей сигналов (real-time обновление
        # админ-панели при любых изменениях данных).
        from main import signals_admin  # noqa: F401
