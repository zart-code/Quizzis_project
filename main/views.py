"""Файл функций views"""

# pylint: disable=no-member

import logging
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.db.models import Count, Avg, Q, F, IntegerField
from django.db.models.functions import Coalesce
from .forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models import Quiz
from .forms import CustomUserCreationForm, StyledAuthenticationForm

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
    return render(request, "main_page.html")


def register_page(request):
    """Страница регистрации"""
    return _handle_form(
        request,
        form_class=CustomUserCreationForm,
        template_name="register.html",
        success_url="main_page",
    )


def login_page(request):
    """Страница логина (вход в систему)"""
    next_url = request.GET.get("next") or request.POST.get("next", "")

    if request.method == "POST":
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(
                "Успешный вход пользователя: %s (IP: %s)",
                user.username,
                request.META.get("REMOTE_ADDR"),
            )
            # Редиректим на next, если он есть и безопасен (начинается с /)
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("main_page")
        else:
            logger.warning(
                "Ошибка валидации формы StyledAuthenticationForm: %s (IP: %s)",
                form.errors,
                request.META.get("REMOTE_ADDR"),
            )
    else:
        form = StyledAuthenticationForm(request)

    return render(request, "login_page.html", {"form": form, "next": next_url})


def logout_view(request):
    """Выход из системы."""
    if request.user.is_authenticated:
        logger.info(
            "Пользователь %s вышел из системы (IP: %s)",
            request.user.username,
            request.META.get("REMOTE_ADDR"),
        )
    logout(request)
    return redirect("main_page")


def quizzes_view(request):
    """Страница квизов."""
    sort_type = request.GET.get("sort", "new")

    current_revision_filter = Q(
        results__completed=True,
        results__revision=F("current_revision"),
    )

    quizzes = (
        Quiz.objects.filter(status=Quiz.ACTIVE)
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
        .order_by("-created_at")
    )

    logger.info(
        "Просмотр квизов: пользователь %s, сортировка=%s, найдено квизов=%d (IP: %s)",
        request.user.username if request.user.is_authenticated else "Anonymous",
        sort_type,
        quizzes.count(),
        request.META.get("REMOTE_ADDR"),
    )

    context = {
        "current_sort": sort_type,
        "quizzes": quizzes,
    }
    return render(request, "quizzes_view.html", context)


def join_by_code(request):
    """Вход в лобби по коду с главной страницы."""
    if request.method == "POST":
        pin = request.POST.get("pin", "").strip().upper()
        if pin:
            return redirect("join_lobby", pin=pin)
    return redirect("main_page")


def my_quizzes(request):
    """Страница квиза (учителя)"""
    logger.info(
        "Пользователь %s перешёл на 'Мои квизы' (IP: %s)",
        request.user.username if request.user.is_authenticated else "Anonymous",
        request.META.get("REMOTE_ADDR"),
    )
    return render(request, "my_quizzes.html")
