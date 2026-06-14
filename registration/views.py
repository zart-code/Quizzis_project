from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
import logging

from main.forms import CustomUserCreationForm, StyledAuthenticationForm
from main.views import logger


logger = logging.getLogger(__name__)


# Create your views here.
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
