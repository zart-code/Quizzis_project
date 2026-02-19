from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm

def main_page(request):
    """Главная страница (меню)."""
    return render(request, 'main_page.html')

def login_page(request):
    """Авторизация пользователя."""
    if request.method == 'POST':
        print(request)
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('main_page')
            else:
                # Неверные данные – показываем форму с ошибкой
                context = {'title': 'Войти в аккаунт', 'form': form}
                return render(request, 'login_page.html', context)
        else:
            context = {'title': 'Войти в аккаунт', 'form': form}
            return render(request, 'login_page.html', context)
    else:
        form = AuthenticationForm()

    context = {'title': 'Войти в аккаунт', 'form': form}
    return render(request, 'login_page.html', context)

def register_page(request):
    """Регистрация нового пользователя."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # автоматический вход после регистрации
            return redirect('main_page')
        else:
            context = {'title': 'Регистрация', 'form': form}
            return render(request, 'register.html', context)
    else:
        form = CustomUserCreationForm()

    context = {'title': 'Регистрация', 'form': form}
    return render(request, 'register.html', context)

def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('main_page')