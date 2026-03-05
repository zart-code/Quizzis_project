from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm
# импортируем функционал из отдельных файлов в папке views_features
from main.views_features.views_profile import *
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin  # если нужна авторизация, но для теста можно без
from .models import CustomUser, Achievement, UserAchievement


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
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('main_page')
        else:
            return render(request, 'login_page.html', {'form': form})
    else:
        form = AuthenticationForm()

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


class UserListView(ListView):
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'


class UserDetailView(DetailView):
    '''дорабатывается'''
    model = CustomUser
    template_name = 'users/user_detail.html'
    context_object_name = 'user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем форму для добавления достижения
        context['form'] = UserAchievementForm()
        # Получаем все доступные достижения (можно для подсказки)
        context['achievements'] = Achievement.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = UserAchievementForm(request.POST)
        if form.is_valid():
            # Создаем запись, но не сохраняем сразу, чтобы добавить пользователя
            user_achievement = form.save(commit=False)
            user_achievement.user = self.object
            user_achievement.save()
            # Может быть, добавить баллы за достижение?
            # Например, self.object.point_count += user_achievement.achievement.points_reward
            # self.object.save()
            return redirect('user_detail', pk=self.object.pk)
        # Если форма не валидна, возвращаем страницу с ошибками
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)