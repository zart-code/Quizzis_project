from django.contrib.auth import login, logout
from django.shortcuts import render, redirect

from main.forms import CustomUserCreationForm, StyledAuthenticationForm
from main.views import _handle_form, logger


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
