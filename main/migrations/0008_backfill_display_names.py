"""
Миграция данных: заполнение display_name для существующих записей.

Для всех GameParticipant и QuizResult с привязанным пользователем и пустым display_name
устанавливает display_name на основе first_name (если непустое) или username.
"""

from django.db import migrations


def backfill_display_names(apps, schema_editor):
    """Заполняет display_name для существующих записей GameParticipant и QuizResult."""
    GameParticipant = apps.get_model("main", "GameParticipant")
    QuizResult = apps.get_model("main", "QuizResult")

    # Обработка GameParticipant
    participants = GameParticipant.objects.filter(
        user__isnull=False,
        display_name="",
    ).select_related("user")

    for participant in participants:
        first_name = participant.user.first_name
        if first_name and first_name.strip():
            participant.display_name = first_name.strip()
        else:
            participant.display_name = participant.user.username
        participant.save(update_fields=["display_name"])

    # Обработка QuizResult
    results = QuizResult.objects.filter(
        user__isnull=False,
        display_name="",
    ).select_related("user")

    for result in results:
        first_name = result.user.first_name
        if first_name and first_name.strip():
            result.display_name = first_name.strip()
        else:
            result.display_name = result.user.username
        result.save(update_fields=["display_name"])


def reverse_backfill(apps, schema_editor):
    """Обратная миграция: очищает display_name у всех записей."""
    GameParticipant = apps.get_model("main", "GameParticipant")
    QuizResult = apps.get_model("main", "QuizResult")

    GameParticipant.objects.all().update(display_name="")
    QuizResult.objects.all().update(display_name="")


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0007_alter_gameparticipant_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_display_names, reverse_backfill),
    ]
