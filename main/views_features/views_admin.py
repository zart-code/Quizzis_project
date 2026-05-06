"""Views для панели администратора"""

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count
from main.models import Quiz, Profile


def admin_required(view_func):
    """Декоратор: доступ только для администраторов"""

    @login_required(login_url="login_page")
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.is_admin:
            messages.error(request, "Доступ запрещён.")
            return redirect("main_page")
        return view_func(request, *args, **kwargs)

    return wrapper


@admin_required
def admin_panel_view(request):
    """Главная страница панели администратора"""
    total_users = User.objects.count()
    total_quizzes = Quiz.objects.count()
    total_banned_users = Profile.objects.filter(is_banned=True).count()
    total_admins = Profile.objects.filter(role=Profile.ADMIN).count()

    users = (
        User.objects.annotate(quiz_count=Count("created_quizzes"))
        .select_related("profile")
        .order_by("id")
    )

    quizzes = (
        Quiz.objects.select_related("creator")
        .annotate(question_count=Count("questions"))
        .order_by("-created_at")
    )

    context = {
        "total_users": total_users,
        "total_quizzes": total_quizzes,
        "total_banned_users": total_banned_users,
        "total_admins": total_admins,
        "users": users,
        "quizzes": quizzes,
    }
    return render(request, "admin_panel.html", context)


@admin_required
def admin_ban_user_view(request, user_id):
    """Заблокировать / разблокировать пользователя"""
    if request.method == "POST":
        target = get_object_or_404(User, id=user_id)
        # Нельзя банить самого себя или другого админа
        if target == request.user:
            messages.error(request, "Нельзя заблокировать самого себя.")
            return redirect("admin_panel")
        profile, _ = Profile.objects.get_or_create(user=target)
        profile.is_banned = not profile.is_banned
        profile.save()
        action = "заблокирован" if profile.is_banned else "разблокирован"
        messages.success(request, f"Пользователь {target.username} {action}.")
    return redirect("admin_panel")


@admin_required
def admin_delete_quiz_view(request, quiz_id):
    """Удалить квиз"""
    if request.method == "POST":
        quiz = get_object_or_404(Quiz, id=quiz_id)
        title = quiz.title
        quiz.delete()
        messages.success(request, f"Квиз «{title}» удалён.")
    return redirect("admin_panel")


@admin_required
def admin_unpublish_quiz_view(request, quiz_id):
    """Вернуть квиз в черновик"""
    if request.method == "POST":
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.status != Quiz.DRAFT:
            quiz.status = Quiz.DRAFT
            quiz.save(update_fields=["status"])
            messages.success(request, f"Квиз «{quiz.title}» возвращён в черновик.")
        else:
            messages.info(request, f"Квиз «{quiz.title}» уже находится в черновиках.")
    return redirect("admin_panel")


@admin_required
def api_admin_stats_view(request):
    """API: текущая статистика для авто-обновления карточек"""
    data = {
        "total_users": User.objects.count(),
        "total_quizzes": Quiz.objects.count(),
        "total_admins": Profile.objects.filter(role=Profile.ADMIN).count(),
        "total_banned_users": Profile.objects.filter(is_banned=True).count(),
    }
    return JsonResponse(data)


@admin_required
def api_admin_users_view(request):
    """API: список пользователей для авто-обновления таблицы"""
    users = (
        User.objects.annotate(quiz_count=Count("created_quizzes"))
        .select_related("profile")
        .order_by("id")
        .values(
            "id",
            "username",
            "email",
            "date_joined",
            "quiz_count",
            "profile__role",
            "profile__is_banned",
        )
    )
    return JsonResponse({"users": list(users)}, json_dumps_params={"default": str})


@admin_required
def api_admin_quizzes_view(request):
    """API: список квизов для авто-обновления таблицы"""
    quizzes = (
        Quiz.objects.select_related("creator")
        .annotate(question_count=Count("questions"))
        .order_by("-created_at")
        .values(
            "id",
            "title",
            "status",
            "created_at",
            "question_count",
            "creator__id",
            "creator__username",
        )
    )
    return JsonResponse({"quizzes": list(quizzes)}, json_dumps_params={"default": str})
