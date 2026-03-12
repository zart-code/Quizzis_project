from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, StyledAuthenticationForm

# импортируем функционал из отдельных файлов в папке views_features
from main.views_features.views_profile import *
from main.views_features.views_quiz import *
from main.views_features.views_lobby import *
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin  # если нужна авторизация, но для теста можно без
from .models import Achievement, UserAchievement


def main_page(request):
    """Главная страница (меню)."""
    return render(request, 'main_page.html')


def register_page(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('main_page')
        else:
            # Ошибки валидации - показываем форму с ошибками
            return render(request, 'register.html', {'form': form})
    else:
        form = CustomUserCreationForm()

    return render(request, 'register.html', {'form': form})


def login_page(request):
    if request.method == 'POST':
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('main_page')
        else:
            return render(request, 'login_page.html', {'form': form})
    else:
        form = StyledAuthenticationForm()

    return render(request, 'login_page.html', {'form': form})


def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('main_page')


def quizzes_view(request):
    sort_type = request.GET.get('sort', 'new')

    context = {
        'current_sort': sort_type,
    }
    return render(request, 'quizzes_view.html', context)


def my_quizzes(request):
    return render(request, 'my_quizzes.html')
