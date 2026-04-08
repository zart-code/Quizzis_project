"""Главное приложение"""
from django.apps import AppConfig


class MainConfig(AppConfig):
    """Настройки приложения"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
