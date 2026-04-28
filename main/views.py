"""Файл функций views"""

from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.db.models import Count, Avg, Q
from .forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models import Quiz


def _handle_form(request,
                 form_class,
                 template_name,
                 success_url,
                 extra_form_kwargs=None,
                 needs_request=False):
    """Создание и проверка валидности формы"""
    if extra_form_kwargs is None:
        extra_form_kwargs = {}

    if request.method == 'POST':
        # Создаём связанную форму с данными из POST
        if needs_request:
            form = form_class(request, data=request.POST)
        else:
            form = form_class(request.POST)

        if form.is_valid():
            if form_class == CustomUserCreationForm:
                user = form.save()
                login(request, user)
            elif form_class == StyledAuthenticationForm:
                user = form.get_user()
                login(request, user)
            return redirect(success_url)
        # Если форма не валидна, продолжим и вернём её же (с ошибками)
    else:
        # GET-запрос: создаём пустую (несвязанную) форму
        form = form_class(**extra_form_kwargs)

    return render(request, template_name, {'form': form})


def main_page(request):
    """Главная страница (меню)."""
    return render(request, 'main_page.html')


def register_page(request):
    """Страница регистрации"""
    return _handle_form(
        request,
        form_class=CustomUserCreationForm,
        template_name='register.html',
        success_url='main_page'
    )


def login_page(request):
    """Страница логина (вход в систему)"""
    return _handle_form(
        request,
        form_class=StyledAuthenticationForm,
        template_name='login_page.html',
        success_url='main_page',
        extra_form_kwargs={'request': request},
        needs_request=True
    )


def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('main_page')


def quizzes_view(request):
    """Страница квизов"""
    sort_type = request.GET.get('sort', 'new')
    quizzes = (
        Quiz.objects
        .filter(status=Quiz.ACTIVE)
        .select_related('creator')
        .annotate(
            total_questions=Count('questions', distinct=True),
            passed_count=Count(
                'results',
                filter=Q(results__completed=True),
                distinct=True,
            ),
            avg_score_percent=Avg(
                'results__score_percent',
                filter=Q(results__completed=True),
            ),
            avg_score_points=Avg(
                'results__score',
                filter=Q(results__completed=True),
            ),
            avg_max_points=Avg(
                'results__max_score',
                filter=Q(results__completed=True),
            ),
        )
        .order_by('-created_at')
    )

    context = {
        'current_sort': sort_type,
        'quizzes': quizzes,
    }
    return render(request, 'quizzes_view.html', context)


def my_quizzes(request):
    """Страница квиза (учителя)"""
    return render(request, 'my_quizzes.html')
