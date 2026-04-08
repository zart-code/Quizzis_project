"""Файл функций views"""
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm, StyledAuthenticationForm


def main_page(request):
    """Главная страница (меню)."""
    return render(request, 'main_page.html')


def register_page(request):
    """Страница регистрации"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('main_page')
        # Ошибки валидации - показываем форму с ошибками
        return render(request, 'register.html', {'form': form})
    form = CustomUserCreationForm()

    return render(request, 'register.html', {'form': form})


def login_page(request):
    """Страница логина (вход в систему)"""
    if request.method == 'POST':
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('main_page')
        return render(request, 'login_page.html', {'form': form})
    form = StyledAuthenticationForm()

    return render(request, 'login_page.html', {'form': form})


def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('main_page')


def quizzes_view(request):
    """Страница квизов"""
    sort_type = request.GET.get('sort', 'new')

    context = {
        'current_sort': sort_type,
    }
    return render(request, 'quizzes_view.html', context)


def my_quizzes(request):
    """Страница квиза (учителя)"""
    return render(request, 'my_quizzes.html')
