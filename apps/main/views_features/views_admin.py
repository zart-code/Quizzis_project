"""Views для панели администратора"""

import logging

# pylint: disable=no-member,unused-argument

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Case, When, IntegerField, F, Q
from django.utils import timezone
from apps.quiz.models import Quiz, QuizReport
from apps.registration.models import Profile

logger = logging.getLogger(__name__)


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
    total_quizzes = Quiz.objects.filter(is_deleted=False).count()
    total_banned_users = Profile.objects.filter(is_banned=True).count()
    total_admins = Profile.objects.filter(role=Profile.ADMIN).count()
    total_pending_reports = QuizReport.objects.filter(
        status=QuizReport.PENDING,
        quiz__is_deleted=False,
    ).count()

    users = (
        User.objects.annotate(
            quiz_count=Count(
                "created_quizzes", filter=Q(created_quizzes__is_deleted=False)
            )
        )
        .select_related("profile")
        .order_by("id")
    )

    quizzes = (
        Quiz.objects.filter(is_deleted=False)
        .select_related("creator")
        .annotate(
            question_count=Case(
                When(
                    current_revision__isnull=False,
                    then=F("current_revision__question_count"),
                ),
                default=Count("questions"),
                output_field=IntegerField(),
            )
        )
        .order_by("-created_at")
    )
    reports = (
        QuizReport.objects.filter(
            quiz__is_deleted=False,
        )
        .select_related(
            "quiz",
            "quiz__creator",
            "reporter",
            "reviewed_by",
        )
        .order_by("-created_at")[:20]
    )

    context = {
        "total_users": total_users,
        "total_quizzes": total_quizzes,
        "total_banned_users": total_banned_users,
        "total_admins": total_admins,
        "total_pending_reports": total_pending_reports,
        "users": users,
        "quizzes": quizzes,
        "reports": reports,
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
        logger.info(
            "Администратор %s %s пользователя %s (ID: %d) (IP: %s)",
            request.user.username,
            action,
            target.username,
            target.id,
            request.META.get("REMOTE_ADDR"),
        )
        messages.success(request, f"Пользователь {target.username} {action}.")
    return redirect("admin_panel")


@admin_required
def admin_change_user_role_view(request, user_id):
    """Изменить роль пользователя (учитель/ученик)."""
    if request.method == "POST":
        target = get_object_or_404(User, id=user_id)
        if target == request.user:
            messages.error(request, "Нельзя менять свою роль.")
            return redirect("admin_panel")

        profile, _ = Profile.objects.get_or_create(user=target)
        if profile.is_admin or profile.role == Profile.ADMIN:
            messages.error(request, "Нельзя менять роль администратора.")
            return redirect("admin_panel")

        new_role = request.POST.get("role")
        if new_role not in [Profile.TEACHER, Profile.STUDENT]:
            messages.error(request, "Неверная роль.")
            return redirect("admin_panel")

        profile.role = new_role
        profile.is_admin = False
        profile.save(update_fields=["role", "is_admin"])

        logger.info(
            "Администратор %s изменил роль пользователя %s (ID: %d) на %s (IP: %s)",
            request.user.username,
            target.username,
            target.id,
            new_role,
            request.META.get("REMOTE_ADDR"),
        )
        messages.success(
            request,
            f"Роль пользователя {target.username} изменена на {'Учитель' if new_role == Profile.TEACHER else 'Ученик'}.",
        )
    return redirect("admin_panel")


@admin_required
def admin_delete_quiz_view(request, quiz_id):
    """Удалить квиз (мягкое удаление)"""
    if request.method == "POST":
        quiz = get_object_or_404(Quiz, id=quiz_id)
        title = quiz.title
        with transaction.atomic():
            quiz.is_deleted = True
            quiz.status = Quiz.DRAFT
            quiz.save(update_fields=["is_deleted", "status"])

        logger.info(
            "Администратор %s удалил квиз «%s» (ID: %d) (IP: %s)",
            request.user.username,
            title,
            quiz_id,
            request.META.get("REMOTE_ADDR"),
        )
        messages.success(request, f"Квиз «{title}» удалён.")
    return redirect("admin_panel")


@admin_required
def admin_unpublish_quiz_view(request, quiz_id):
    """Вернуть квиз в черновик"""
    if request.method == "POST":
        quiz = get_object_or_404(Quiz, id=quiz_id, is_deleted=False)
        if quiz.status != Quiz.DRAFT:
            quiz.status = Quiz.DRAFT
            quiz.save(update_fields=["status"])
            logger.info(
                "Администратор %s вернул в черновики квиз «%s» (ID: %d) (IP: %s)",
                request.user.username,
                quiz.title,
                quiz_id,
                request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, f"Квиз «{quiz.title}» возвращён в черновик.")
        else:
            messages.info(
                request,
                f"Квиз «{quiz.title}» уже находится в черновиках.",
            )
    return redirect("admin_panel")


@admin_required
def admin_accept_report_view(request, report_id):
    """Подтвердить жалобу и вернуть квиз в черновик."""
    if request.method == "POST":
        report = get_object_or_404(QuizReport, id=report_id)
        admin_comment = request.POST.get("admin_comment", "").strip()

        with transaction.atomic():
            report.status = QuizReport.ACCEPTED
            report.admin_comment = admin_comment
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.save(
                update_fields=[
                    "status",
                    "admin_comment",
                    "reviewed_by",
                    "reviewed_at",
                ]
            )

            if report.quiz.status != Quiz.DRAFT:
                report.quiz.status = Quiz.DRAFT
                report.quiz.save(update_fields=["status"])

        messages.success(
            request,
            f"Жалоба на квиз «{report.quiz.title}» подтверждена.",
        )
    return redirect("admin_panel")


@admin_required
def admin_reject_report_view(request, report_id):
    """Отклонить жалобу на квиз."""
    if request.method == "POST":
        report = get_object_or_404(QuizReport, id=report_id)
        report.status = QuizReport.REJECTED
        report.admin_comment = request.POST.get("admin_comment", "").strip()
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(
            update_fields=[
                "status",
                "admin_comment",
                "reviewed_by",
                "reviewed_at",
            ]
        )
        messages.success(
            request,
            f"Жалоба на квиз «{report.quiz.title}» отклонена.",
        )
    return redirect("admin_panel")
