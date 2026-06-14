"""Views для ИИ-генерации квизов (двухшаговая, Google Gemini)."""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from apps.quiz.models import Quiz
from apps.registration.models import Profile
from apps.main.services.quiz_ai_generator import (
    generate_questions,
    generate_quiz_from_questions,
)
from apps.main.services.quiz_revisions import create_revision_from_payloads

logger = logging.getLogger(__name__)


@login_required
def ai_generate_page_view(request):
    """Страница генерации квиза через ИИ."""
    profile = getattr(request.user, "profile", None)
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        return JsonResponse(
            {"error": "Доступ только для учителей и администраторов."},
            status=403,
        )
    return render(request, "ai_generate.html")


@login_required
@require_POST
def ai_generate_questions_view(request):
    """
    Шаг 1: Генерация списка вопросов (только тексты).

    POST JSON: {"topic": "...", "num_questions": 5, "difficulty": "medium"}
    Ответ: {"title": "...", "questions": ["...", "..."]}
    """
    profile = getattr(request.user, "profile", None)
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        return JsonResponse({"error": "Доступ запрещён."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Невалидный JSON."}, status=400)

    topic = body.get("topic", "").strip()
    if not topic:
        return JsonResponse({"error": "Укажите тему квиза."}, status=400)

    num_questions = body.get("num_questions", 5)
    if not isinstance(num_questions, int) or num_questions < 1:
        num_questions = 5
    if num_questions > 20:
        num_questions = 20

    difficulty = body.get("difficulty", "medium")
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    logger.info(
        "Пользователь %s запросил генерацию вопросов: тема='%s', кол-во=%d (IP: %s)",
        request.user.username,
        topic,
        num_questions,
        request.META.get("REMOTE_ADDR"),
    )

    result = generate_questions(
        topic=topic,
        num_questions=num_questions,
        difficulty=difficulty,
    )

    if not result["success"]:
        return JsonResponse({"error": result["error"]}, status=502)

    return JsonResponse(result["data"])


@login_required
@require_POST
def ai_generate_quiz_view(request):
    """
    Шаг 2: Генерация полного квиза по списку вопросов.

    POST JSON: {"title": "...", "questions": ["вопрос 1", "вопрос 2", ...]}
    Ответ: полный JSON квиза с ответами.
    """
    profile = getattr(request.user, "profile", None)
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        return JsonResponse({"error": "Доступ запрещён."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Невалидный JSON."}, status=400)

    title = body.get("title", "").strip()
    if not title:
        return JsonResponse({"error": "Укажите название квиза."}, status=400)

    questions = body.get("questions", [])
    if not isinstance(questions, list) or not questions:
        return JsonResponse({"error": "Список вопросов пуст."}, status=400)

    # Фильтруем пустые
    questions = [str(q).strip() for q in questions if str(q).strip()]
    if not questions:
        return JsonResponse({"error": "Все вопросы пустые."}, status=400)

    if len(questions) > 20:
        questions = questions[:20]

    logger.info(
        "Пользователь %s запросил генерацию квиза: title='%s', вопросов=%d (IP: %s)",
        request.user.username,
        title,
        len(questions),
        request.META.get("REMOTE_ADDR"),
    )

    result = generate_quiz_from_questions(
        title=title,
        questions=questions,
    )

    if not result["success"]:
        return JsonResponse({"error": result["error"]}, status=502)

    return JsonResponse(result["data"])


@login_required
@require_POST
def ai_save_quiz_view(request):
    """
    Шаг 3: Сохранение сгенерированного квиза (как при обычном создании).
    """
    profile = getattr(request.user, "profile", None)
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        return redirect("main_page")

    from apps.main.services.quiz_revisions import collect_question_payloads_from_post

    title = request.POST.get("title", "").strip()
    if not title:
        return redirect("ai_generate_page")

    question_payloads = collect_question_payloads_from_post(request)
    if not question_payloads:
        return redirect("ai_generate_page")

    quiz = Quiz.objects.create(
        title=title,
        creator=request.user,
        status=Quiz.DRAFT,
    )

    create_revision_from_payloads(
        quiz=quiz,
        title=title,
        question_payloads=question_payloads,
    )

    logger.info(
        "Пользователь %s создал AI-квиз «%s» (ID: %d) (IP: %s)",
        request.user.username,
        title,
        quiz.id,
        request.META.get("REMOTE_ADDR"),
    )

    return redirect("my_quizzes")
