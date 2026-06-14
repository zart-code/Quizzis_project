"""Файл функций views"""

# pylint: disable=no-member

import logging
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.urls import reverse
from django.db.models import Count, Avg, Q, F
from .forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models_packet.quiz_models import Quiz
from main.views_features.views_lobby import _get_request_user

# Настройка логгера
logger = logging.getLogger(__name__)


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _handle_form(
    request,
    form_class,
    template_name,
    success_url,
    extra_form_kwargs=None,
    needs_request=False,
):
    """Создание и проверка валидности формы"""
    if extra_form_kwargs is None:
        extra_form_kwargs = {}

    if request.method == "POST":
        if needs_request:
            form = form_class(request, data=request.POST)
        else:
            form = form_class(request.POST)

        if form.is_valid():
            if form_class == CustomUserCreationForm:
                user = form.save()
                login(request, user)
                logger.info(
                    "Успешная регистрация пользователя: %s (IP: %s)",
                    user.username,
                    request.META.get("REMOTE_ADDR"),
                )
            elif form_class == StyledAuthenticationForm:
                user = form.get_user()
                login(request, user)
                logger.info(
                    "Успешный вход пользователя: %s (IP: %s)",
                    user.username,
                    request.META.get("REMOTE_ADDR"),
                )
            return redirect(success_url)
        else:
            # Логируем ошибки валидации формы
            logger.warning(
                "Ошибка валидации формы %s: %s (IP: %s)",
                form_class.__name__,
                form.errors,
                request.META.get("REMOTE_ADDR"),
            )
    else:
        # GET-запрос: создаём пустую (несвязанную) форму
        form = form_class(**extra_form_kwargs)

    return render(request, template_name, {"form": form})


def main_page(request):
    """Главная страница (меню)."""
    logger.info(
        "Пользователь %s посетил главную страницу (IP: %s)",
        request.user.username if request.user.is_authenticated else "Anonymous",
        request.META.get("REMOTE_ADDR"),
    )

    # Популярные квизы для секции "Популярное сейчас"
    current_revision_filter = Q(
        results__completed=True,
        results__revision=F("current_revision"),
    )

    popular_quizzes = (
        Quiz.objects.filter(status=Quiz.ACTIVE, is_deleted=False)
        .select_related("creator", "current_revision")
        .annotate(
            passed_count=Count(
                "results",
                filter=current_revision_filter,
                distinct=True,
            ),
            avg_score_percent=Avg(
                "results__score_percent",
                filter=current_revision_filter,
            ),
            avg_score_points=Avg(
                "results__score",
                filter=current_revision_filter,
            ),
            avg_max_points=Avg(
                "results__max_score",
                filter=current_revision_filter,
            ),
        )
        .order_by("-passed_count", "-created_at")[:3]
    )

    # Вычисляем максимальное количество прохождений для шкалы популярности
    max_passed = max((q.passed_count for q in popular_quizzes), default=1) or 1
    for quiz in popular_quizzes:
        quiz.popularity_percent = int(quiz.passed_count / max_passed * 100)

    context = {
        "join_pin_prefill": request.GET.get("pin", ""),
        "highlight_nickname": (
            request.GET.get("highlight") == "1" and not request.user.is_authenticated
        ),
        "show_kicked_modal": request.GET.get("kicked") == "1",
        "popular_quizzes": popular_quizzes,
    }
    return render(request, "main_page.html", context)


def quizzes_view(request):
    """Страница квизов."""
    sort_type = request.GET.get("sort", "new")
    search_query = request.GET.get("search", "").strip()

    current_revision_filter = Q(
        results__completed=True,
        results__revision=F("current_revision"),
    )

    quizzes = (
        Quiz.objects.filter(status=Quiz.ACTIVE, is_deleted=False)
        .select_related("creator", "current_revision")
        .annotate(
            passed_count=Count(
                "results",
                filter=current_revision_filter,
                distinct=True,
            ),
            avg_score_percent=Avg(
                "results__score_percent",
                filter=current_revision_filter,
            ),
            avg_score_points=Avg(
                "results__score",
                filter=current_revision_filter,
            ),
            avg_max_points=Avg(
                "results__max_score",
                filter=current_revision_filter,
            ),
        )
    )

    # Фильтрация по поисковому запросу (нечёткий поиск — содержит подстроку)
    if search_query:
        quizzes = quizzes.filter(title__icontains=search_query)

    # Сортировка
    if sort_type == "popular":
        quizzes = quizzes.order_by("-passed_count", "-created_at")
    elif sort_type == "best":
        quizzes = quizzes.order_by(
            F("avg_score_percent").desc(nulls_last=True), "-created_at"
        )
    else:
        quizzes = quizzes.order_by("-created_at")

    logger.info(
        "Просмотр квизов: пользователь %s, сортировка=%s, поиск='%s', найдено квизов=%d (IP: %s)",
        request.user.username if request.user.is_authenticated else "Anonymous",
        sort_type,
        search_query,
        quizzes.count(),
        request.META.get("REMOTE_ADDR"),
    )

    context = {
        "current_sort": sort_type,
        "search_query": search_query,
        "quizzes": quizzes,
    }
    return render(request, "quizzes_view.html", context)


def join_by_code(request):
    """Вход в лобби по коду с главной страницы."""
    from django.contrib import messages
    from main.models import GameSession

    if request.method == "POST":
        pin = request.POST.get("pin", "").strip().upper()
        if pin:
            session = GameSession.objects.filter(pin=pin).first()
            if session is not None:
                # Не создаём гостя для завершённой сессии
                if session.status == GameSession.FINISHED:
                    messages.error(
                        request,
                        "Эта игра уже завершена. Присоединиться невозможно.",
                    )
                    return redirect("main_page")
                if not request.user.is_authenticated:
                    nickname = request.POST.get("nickname", "").strip()
                    # Если это первый раз (нет guest_user_id), очищаем флаг
                    # Если это повторный раз (есть guest_user_id), обновляем ник существующего гостя
                    if not request.session.get("guest_user_id"):
                        request.session.pop("guest_nickname_set", None)
                    # Устанавливаем флаг того, что ник был введён
                    request.session["guest_nickname_set"] = True
                    _get_request_user(request, guest_name=nickname)
                return redirect(
                    f"{reverse('join_lobby', kwargs={'pin': pin})}?from_code=1"
                )
            else:
                messages.error(
                    request,
                    f"Лобби с кодом «{pin}» не найдено. Проверьте код и попробуйте снова.",
                )
    return redirect("main_page")
