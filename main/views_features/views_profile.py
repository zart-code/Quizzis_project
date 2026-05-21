"""Views для профиля"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q
from main.models import Achievement, Quiz, QuizResult, UserAchievement

logger = logging.getLogger(__name__)


@login_required(login_url="login_page")
def profile_view(request, user_id=None):
    """Страница профиля пользователя. Если передан user_id и запрос от админа — показывает чужой профиль."""

    if user_id is not None:
        # Только админ может смотреть чужой профиль
        if not request.user.profile.is_admin:
            return redirect("profile")
        user = get_object_or_404(User, id=user_id)
        is_admin_view = True
    else:
        user = request.user
        is_admin_view = False

    total_quizzes = Quiz.objects.count()
    completed_quizzes = (
        QuizResult.objects.filter(user=user, completed=True)
        .values("quiz")
        .distinct()
        .count()
    )
    total_played_quizzes = QuizResult.objects.filter(user=user, completed=True).count()
    is_student = user.profile.role == "student"

    score_stats = QuizResult.objects.filter(user=user, completed=True).aggregate(
        avg_score=Avg("score_percent")
    )

    average_score = score_stats["avg_score"] or 0

    category_stats = (
        Quiz.objects.values("category__name")
        .annotate(
            quizzes_taken=Count("results", filter=Q(results__user=user)),
            average_score=Avg("results__score_percent", filter=Q(results__user=user)),
        )
        .filter(quizzes_taken__gt=0)
    )

    recent_quiz_history = (
        QuizResult.objects.filter(user=user, completed=True)
        .select_related("quiz", "quiz__creator", "revision")
        .order_by("-completed_at")
    )[:5]

    user_achievements = UserAchievement.objects.filter(user=user).select_related(
        "achievement"
    )
    unlocked_achievement_ids = user_achievements.values_list(
        "achievement_id", flat=True
    )

    all_achievements = Achievement.objects.all()
    achievements = []

    for achievement in all_achievements:
        achievements.append(
            {
                "id": achievement.id,
                "name": achievement.name,
                "description": achievement.description,
                "icon": achievement.icon,
                "unlocked": achievement.id in unlocked_achievement_ids,
            }
        )

    context = {
        "profile_user": user,
        "total_quizzes": total_quizzes,
        "completed_quizzes": completed_quizzes,
        "total_played_quizzes": total_played_quizzes,
        "average_score": average_score,
        "category_stats": category_stats,
        "recent_quiz_history": recent_quiz_history,
        "achievements": achievements,
        "is_admin_view": is_admin_view,
        "is_student": is_student,
    }

    if is_admin_view:
        logger.info(
            "Администратор %s просматривает профиль пользователя %s (ID: %d) (IP: %s)",
            request.user.username,
            user.username,
            user.id,
            request.META.get("REMOTE_ADDR"),
        )
    else:
        logger.info(
            "Пользователь %s просматривает свой профиль (IP: %s)",
            request.user.username,
            request.META.get("REMOTE_ADDR"),
        )
    return render(request, "profile.html", context)


@login_required(login_url="login_page")
def profile_history_view(request, user_id=None):
    """Полная история прохождений пользователя."""
    if user_id is not None:
        if not request.user.profile.is_admin:
            return redirect("profile")
        user = get_object_or_404(User, id=user_id)
        is_admin_view = True
    else:
        user = request.user
        is_admin_view = False

    quiz_history = (
        QuizResult.objects.filter(user=user, completed=True)
        .select_related("quiz", "quiz__creator", "revision")
        .order_by("-completed_at")
    )

    context = {
        "profile_user": user,
        "quiz_history": quiz_history,
        "is_admin_view": is_admin_view,
    }
    return render(request, "profile_history.html", context)


@login_required(login_url="login_page")
def edit_profile_view(request, user_id=None):
    """Редактирование профиля. user_id задаётся только при вызове от админа."""
    if user_id is not None:
        if not request.user.profile.is_admin:
            return redirect("profile")
        target_user = get_object_or_404(User, id=user_id)
        is_admin_edit = True
    else:
        target_user = request.user
        is_admin_edit = False
    if request.method == "POST":
        user = target_user

        username = request.POST.get("username")
        email = request.POST.get("email")

        if username and username != user.username:
            if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                messages.error(request, "Пользователь с таким именем уже существует")
                return (
                    redirect("admin_edit_user", user_id=user_id)
                    if is_admin_edit
                    else redirect("edit_profile")
                )
            user.username = username

        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, "Пользователь с таким email уже существует")
                return redirect("edit_profile")
            user.email = email

        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")

        if is_admin_edit and not password:
            messages.error(
                request, "При редактировании пользователя нужно указать пароль"
            )
            return redirect("admin_edit_user", user_id=user_id)

        if password:
            if password != password_confirm:
                messages.error(request, "Пароли не совпадают")
                return (
                    redirect("admin_edit_user", user_id=user_id)
                    if is_admin_edit
                    else redirect("edit_profile")
                )
            if len(password) < 8:
                messages.error(request, "Пароль должен быть не менее 8 символов")
                return (
                    redirect("admin_edit_user", user_id=user_id)
                    if is_admin_edit
                    else redirect("edit_profile")
                )
            user.set_password(password)
            if not is_admin_edit:
                update_session_auth_hash(request, user)

        user.save()
        messages.success(request, "Профиль успешно обновлён")
        if is_admin_edit:
            logger.info(
                "Администратор %s отредактировал профиль пользователя %s (ID: %d) (IP: %s)",
                request.user.username,
                target_user.username,
                target_user.id,
                request.META.get("REMOTE_ADDR"),
            )
            return redirect("admin_user_profile", user_id=user_id)
        else:
            logger.info(
                "Пользователь %s отредактировал свой профиль (IP: %s)",
                request.user.username,
                request.META.get("REMOTE_ADDR"),
            )
            return redirect("profile")

    context = {
        "edited_user": target_user,
        "is_admin_edit": is_admin_edit,
    }
    return render(request, "edit_profile.html", context)
