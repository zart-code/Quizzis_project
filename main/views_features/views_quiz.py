"""Views для квизов"""

import logging
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from main.models import Quiz, Profile, QuizResult
from django.views.decorators.http import require_POST
from django.utils import timezone
from main.services.quiz_revisions import (
    build_quiz_form_payload,
    build_quiz_payload_for_edit,
    collect_question_payloads_from_post,
    create_revision_from_payloads,
    get_current_revision,
    get_quiz_max_score,
    get_quiz_questions,
)
from main.services.quiz_scoring import score_question

logger = logging.getLogger(__name__)


def _render_quiz_form(request, *, quiz=None, quiz_payload=None):
    """Единая отрисовка формы создания/редактирования квиза."""
    return render(
        request,
        "create_quiz.html",
        {
            "is_edit": quiz is not None,
            "quiz": quiz,
            "quiz_payload": quiz_payload,
        },
    )


@login_required
def create_quiz_view(request):
    profile = getattr(request.user, "profile", None)

    if profile and profile.is_banned:
        return render(request, "banned_create_quiz.html")

    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        messages.error(
            request,
            "Создавать квизы могут только учителя и администраторы.",
        )
        return redirect("main_page")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        question_payloads = collect_question_payloads_from_post(request)

        if not title:
            messages.error(request, "Название квиза не может быть пустым.")
            return _render_quiz_form(
                request,
                quiz_payload=build_quiz_form_payload(title, question_payloads),
            )

        if not question_payloads:
            messages.error(
                request,
                "Нельзя создать пустой квиз. Добавьте хотя бы один вопрос.",
            )
            return _render_quiz_form(
                request,
                quiz_payload=build_quiz_form_payload(title, question_payloads),
            )

        quiz = Quiz.objects.create(
            title=title,
            creator=request.user,
            status=Quiz.DRAFT,
        )

        create_revision_from_payloads(
            quiz=quiz,
            title=title,
            question_payloads=question_payloads,
        )

        logger.info(
            "Пользователь %s создал новый квиз «%s» (ID: %d) (IP: %s)",
            request.user.username,
            title,
            quiz.id,
            request.META.get("REMOTE_ADDR"),
        )
        return redirect("my_quizzes")

    return _render_quiz_form(request)


@login_required
def my_quizzes_view(request):
    profile = getattr(request.user, "profile", None)
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        messages.error(
            request, 'Раздел "Мои квизы" доступен только учителям и администраторам.'
        )
        return redirect("main_page")

    search_query = request.GET.get("search", "").strip()

    quizzes = Quiz.objects.filter(creator=request.user).order_by("-created_at")

    if search_query:
        quizzes = quizzes.filter(title__icontains=search_query)

    total_questions = 0
    for quiz in quizzes:
        total_questions += quiz.total_questions()
    context = {
        "quizzes": quizzes,
        "total_questions": total_questions,
        "search_query": search_query,
    }
    return render(request, "my_quizzes.html", context)


@login_required
@require_POST
def toggle_quiz_status_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)

    old_status = quiz.status
    if quiz.status == Quiz.DRAFT:
        quiz.status = Quiz.ACTIVE
    else:
        quiz.status = Quiz.DRAFT

    quiz.save()
    logger.info(
        "Пользователь %s изменил статус квиза «%s» с %s на %s (IP: %s)",
        request.user.username,
        quiz.title,
        "черновик" if old_status == Quiz.DRAFT else "активен",
        "активен" if quiz.status == Quiz.ACTIVE else "черновик",
        request.META.get("REMOTE_ADDR"),
    )
    return redirect("my_quizzes")


@login_required
def play_quiz_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if quiz.status == Quiz.DRAFT and quiz.creator != request.user:
        return redirect("quizzes_view")

    questions = get_quiz_questions(quiz)
    current_revision = get_current_revision(quiz)

    if not questions:
        return redirect("my_quizzes")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "finish":
            answers_log = request.session.get(f"quiz_{quiz_id}_log", [])
            score = sum(item["points"] for item in answers_log)
            total = sum(item["max_points"] for item in answers_log)
            score_percent = (score / total * 100) if total else 0

            result_id = request.session.get(f"quiz_{quiz_id}_result_id")
            if result_id:
                QuizResult.objects.filter(
                    id=result_id,
                    user=request.user,
                    quiz=quiz,
                ).update(
                    score=score,
                    max_score=total,
                    score_percent=score_percent,
                    completed=True,
                    completed_at=timezone.now(),
                )

            request.session.pop(f"quiz_{quiz_id}_log", None)
            request.session.pop(f"quiz_{quiz_id}_index", None)
            request.session.pop(f"quiz_{quiz_id}_result_id", None)
            request.session.pop(f"quiz_{quiz_id}_answered", None)

            logger.info(
                "Пользователь %s завершил одиночное прохождение квиза «%s» (ID: %d). Баллы: %d / %d (%.1f%%) (IP: %s)",
                request.user.username,
                quiz.title,
                quiz.id,
                score,
                total,
                score_percent,
                request.META.get("REMOTE_ADDR"),
            )
            return render(
                request,
                "play_quiz.html",
                {
                    "quiz": quiz,
                    "score": score,
                    "total": total,
                    "finished": True,
                },
            )

        if action == "answer":
            index = int(request.POST.get("index", 0))
            question = questions[index]
            timed_out = request.POST.get("timed_out") == "1"
            correct_answer = None

            answered_key = f"quiz_{quiz_id}_answered"
            answered_questions = request.session.get(answered_key, {})
            question_key = str(question.id)

            if question_key in answered_questions:
                stored = answered_questions[question_key]

                if question.question_type == "single":
                    correct_answer = question.answers.filter(is_correct=True).first()

                next_index = index + 1
                is_last = next_index >= len(questions)

                return render(
                    request,
                    "play_quiz.html",
                    {
                        "quiz": quiz,
                        "question": question,
                        "correct_answer": correct_answer,
                        "is_correct": stored["is_correct"],
                        "timed_out": stored["timed_out"],
                        "next_index": next_index,
                        "is_last": is_last,
                        "finished": False,
                        "show_result": True,
                        "earned_points": stored["earned_points"],
                        "question_max_points": stored["max_points"],
                    },
                )

            score_result = score_question(
                question,
                request,
                timed_out=timed_out,
            )
            earned_points = score_result.points
            max_points = score_result.max_points
            is_correct = score_result.is_correct

            if question.question_type == "single":
                correct_answer = question.answers.filter(is_correct=True).first()

            answered_questions[question_key] = {
                "earned_points": earned_points,
                "max_points": max_points,
                "is_correct": is_correct,
                "timed_out": timed_out,
            }
            request.session[answered_key] = answered_questions

            log = request.session.get(f"quiz_{quiz_id}_log", [])
            log.append(
                {
                    "points": earned_points,
                    "max_points": max_points,
                    "correct": is_correct,
                }
            )
            request.session[f"quiz_{quiz_id}_log"] = log

            next_index = index + 1
            is_last = next_index >= len(questions)

            return render(
                request,
                "play_quiz.html",
                {
                    "quiz": quiz,
                    "question": question,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "timed_out": timed_out,
                    "next_index": next_index,
                    "is_last": is_last,
                    "finished": False,
                    "show_result": True,
                    "earned_points": earned_points,
                    "question_max_points": max_points,
                },
            )

        if action == "next":
            index = int(request.POST.get("index", 0))
            question = questions[index]
            return render(
                request,
                "play_quiz.html",
                {
                    "quiz": quiz,
                    "question": question,
                    "index": index,
                    "total": len(questions),
                    "finished": False,
                    "show_result": False,
                },
            )

    result = QuizResult.objects.create(
        user=request.user,
        quiz=quiz,
        revision=current_revision,
        score=0,
        max_score=get_quiz_max_score(quiz),
        score_percent=0,
        completed=False,
    )

    request.session[f"quiz_{quiz_id}_log"] = []
    request.session[f"quiz_{quiz_id}_index"] = 0
    request.session[f"quiz_{quiz_id}_result_id"] = result.id
    request.session[f"quiz_{quiz_id}_answered"] = {}

    return render(
        request,
        "play_quiz.html",
        {
            "quiz": quiz,
            "question": questions[0],
            "index": 0,
            "total": len(questions),
            "finished": False,
            "show_result": False,
        },
    )


@login_required
def edit_quiz_view(request, quiz_id):
    profile = getattr(request.user, "profile", None)

    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        messages.error(
            request,
            "Редактировать квизы могут только учителя и администраторы.",
        )
        return redirect("main_page")

    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        question_payloads = collect_question_payloads_from_post(request)
        quiz_payload = build_quiz_form_payload(title, question_payloads)

        if not title:
            messages.error(request, "Название квиза не может быть пустым.")
            return _render_quiz_form(
                request,
                quiz=quiz,
                quiz_payload=quiz_payload,
            )

        if not question_payloads:
            messages.error(
                request,
                "Нельзя сохранить пустой квиз. Добавьте хотя бы один вопрос.",
            )
            return _render_quiz_form(
                request,
                quiz=quiz,
                quiz_payload=quiz_payload,
            )

        quiz.title = title
        quiz.save(update_fields=["title"])

        create_revision_from_payloads(
            quiz=quiz,
            title=title,
            question_payloads=question_payloads,
        )

        logger.info(
            "Пользователь %s отредактировал квиз «%s» (ID: %d) (IP: %s)",
            request.user.username,
            title,
            quiz.id,
            request.META.get("REMOTE_ADDR"),
        )
        messages.success(request, "Квиз успешно обновлён.")
        return redirect("my_quizzes")

    return _render_quiz_form(
        request,
        quiz=quiz,
        quiz_payload=build_quiz_payload_for_edit(quiz),
    )