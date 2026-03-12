from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Max, Count, Q
from main.forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models import Quiz, QuizResult, UserAchievement, Achievement
from main.models import Achievement, Quiz, QuizResult, UserAchievement


@login_required(login_url='login_page')
def profile_view(request):
    """Страница профиля пользователя."""
    user = request.user

    total_quizzes = Quiz.objects.count()
    completed_quizzes = QuizResult.objects.filter(user=user, completed=True).count()

    score_stats = QuizResult.objects.filter(user=user, completed=True).aggregate(
        avg_score=Avg('score_percent'),
        best_score=Max('score_percent')
    )

    average_score = score_stats['avg_score'] or 0
    best_score = score_stats['best_score'] or 0

    category_stats = Quiz.objects.values('category__name').annotate(
        quizzes_taken=Count('results', filter=Q(results__user=user)),
        average_score=Avg('results__score_percent', filter=Q(results__user=user)),
        best_score=Max('results__score_percent', filter=Q(results__user=user))
    ).filter(quizzes_taken__gt=0)

    status_filter = request.GET.get('status', 'all')
    quiz_history = QuizResult.objects.filter(user=user).select_related('quiz')

    if status_filter == 'completed':
        quiz_history = quiz_history.filter(completed=True)
    elif status_filter == 'in_progress':
        quiz_history = quiz_history.filter(completed=False)

    quiz_history = quiz_history.order_by('-completed_at', '-started_at')[:10]

    user_achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
    unlocked_achievement_ids = user_achievements.values_list('achievement_id', flat=True)

    all_achievements = Achievement.objects.all()
    achievements = []

    for achievement in all_achievements:
        achievements.append({
            'id': achievement.id,
            'name': achievement.name,
            'description': achievement.description,
            'icon': achievement.icon,
            'unlocked': achievement.id in unlocked_achievement_ids
        })

    context = {
        'user': user,
        'total_quizzes': total_quizzes,
        'completed_quizzes': completed_quizzes,
        'average_score': average_score,
        'best_score': best_score,
        'category_stats': category_stats,
        'quiz_history': quiz_history,
        'achievements': achievements,
    }

    return render(request, 'profile.html', context)


@login_required(login_url='login_page')
def edit_profile_view(request):
    """Редактирование профиля пользователя."""
    if request.method == 'POST':
        user = request.user

        username = request.POST.get('username')
        email = request.POST.get('email')

        if username and username != user.username:
            if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                messages.error(request, 'Пользователь с таким именем уже существует')
                return redirect('edit_profile')
            user.username = username

        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, 'Пользователь с таким email уже существует')
                return redirect('edit_profile')
            user.email = email

        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password:
            if password != password_confirm:
                messages.error(request, 'Пароли не совпадают')
                return redirect('edit_profile')
            if len(password) < 8:
                messages.error(request, 'Пароль должен быть не менее 8 символов')
                return redirect('edit_profile')
            user.set_password(password)
            update_session_auth_hash(request, user)

        user.save()
        messages.success(request, 'Профиль успешно обновлен')
        return redirect('profile')

    context = {
        'user': request.user,
    }
    return render(request, 'edit_profile.html', context)


@login_required(login_url='login_page')
def continue_quiz_view(request, quiz_id):
    """Продолжить прохождение квиза."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    return redirect('take_quiz', quiz_id=quiz_id)