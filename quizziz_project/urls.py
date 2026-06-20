"""
Главный файл url проекта
"""

# pylint: disable=duplicate-code

from django.contrib import admin
from django.urls import path, re_path
from django.shortcuts import render
from django.conf import settings
from django.views.static import serve
from apps.main.views import (
    main_page,
    quizzes_view,
    join_by_code,
)
from apps.registration.views import register_page, login_page, logout_view, profile_view, profile_history_view, \
    edit_profile_view
from apps.quiz.views import (
    create_quiz_view,
    my_quizzes_view,
    toggle_quiz_status_view,
    delete_quiz_view,
    report_quiz_view,
    play_quiz_view,
    edit_quiz_view,
)
from apps.game_lobby.views import (
    create_lobby_view,
    lobby_view,
    toggle_lock_view,
    delete_session_view,
    kick_player_view,
    join_lobby_view,
    start_game_view,
    session_play_view,
    submit_answer_view,
    quiz_sessions_list_view,
    advance_question_view,
    session_results_teacher_view,
)
from apps.superuser_app.views import admin_panel_view, admin_ban_user_view, admin_change_user_role_view, \
    admin_delete_quiz_view, admin_unpublish_quiz_view, admin_accept_report_view, admin_reject_report_view
from apps.ai_assist.views import ai_generate_page_view, ai_generate_questions_view, ai_generate_quiz_view, \
    ai_save_quiz_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", main_page, name="main_page"),
    path("login/", login_page, name="login_page"),
    path("register/", register_page, name="register_page"),
    path("logout/", logout_view, name="logout"),
    path("profile/", profile_view, name="profile"),
    path("profile/history/", profile_history_view, name="profile_history"),
    path("profile/edit/", edit_profile_view, name="edit_profile"),
    path("quiz/create/", create_quiz_view, name="create_quiz"),
    path("quiz/<int:quiz_id>/edit/", edit_quiz_view, name="edit_quiz"),
    path("my-quizzes/", my_quizzes_view, name="my_quizzes"),
    path(
        "quiz/<int:quiz_id>/toggle-status/",
        toggle_quiz_status_view,
        name="toggle_quiz_status",
    ),
    path(
        "quiz/<int:quiz_id>/delete/",
        delete_quiz_view,
        name="delete_quiz",
    ),
    path("quiz/<int:quiz_id>/play/", play_quiz_view, name="play_quiz"),
    path("quiz/<int:quiz_id>/report/", report_quiz_view, name="report_quiz"),
    path("quiz/<int:quiz_id>/lobby/create/", create_lobby_view, name="create_lobby"),
    path("lobby/<str:pin>/", lobby_view, name="lobby"),
    path("lobby/<str:pin>/lock/", toggle_lock_view, name="toggle_lock"),
    path("lobby/<str:pin>/delete/", delete_session_view, name="delete_session"),
    path(
        "lobby/<str:pin>/api/kick/<int:participant_id>/",
        kick_player_view,
        name="kick_player",
    ),
    path("join/", join_by_code, name="join_by_code"),
    path("join/<str:pin>/", join_lobby_view, name="join_lobby"),
    path("lobby/<str:pin>/start/", start_game_view, name="start_game"),
    path(
        "lobby/<str:pin>/api/advance-question/",
        advance_question_view,
        name="advance_question",
    ),
    path("session/<str:pin>/play/", session_play_view, name="session_play"),
    path("session/<str:pin>/answer/", submit_answer_view, name="submit_answer"),
    path(
        "quiz/<int:quiz_id>/sessions/",
        quiz_sessions_list_view,
        name="quiz_sessions_list",
    ),
    path(
        "session/<str:pin>/results/teacher/",
        session_results_teacher_view,
        name="session_results_teacher",
    ),
    path("quizzises/", quizzes_view, name="quizzes_view"),
    path("admin-panel/", admin_panel_view, name="admin_panel"),
    path("admin-panel/ban/<int:user_id>/", admin_ban_user_view, name="admin_ban_user"),
    path(
        "admin-panel/change-role/<int:user_id>/",
        admin_change_user_role_view,
        name="admin_change_user_role",
    ),
    path(
        "admin-panel/unpublish-quiz/<int:quiz_id>/",
        admin_unpublish_quiz_view,
        name="admin_unpublish_quiz",
    ),
    path(
        "admin-panel/delete-quiz/<int:quiz_id>/",
        admin_delete_quiz_view,
        name="admin_delete_quiz",
    ),
    path(
        "admin-panel/report/<int:report_id>/accept/",
        admin_accept_report_view,
        name="admin_accept_report",
    ),
    path(
        "admin-panel/report/<int:report_id>/reject/",
        admin_reject_report_view,
        name="admin_reject_report",
    ),
    path("admin-panel/user/<int:user_id>/", profile_view, name="admin_user_profile"),
    path(
        "admin-panel/user/<int:user_id>/history/",
        profile_history_view,
        name="admin_user_history",
    ),
    path(
        "admin-panel/user/<int:user_id>/edit/",
        edit_profile_view,
        name="admin_edit_user",
    ),
    # ИИ-генерация квизов
    path("quiz/ai-generate/", ai_generate_page_view, name="ai_generate_page"),
    path(
        "quiz/ai-generate/questions/",
        ai_generate_questions_view,
        name="ai_generate_questions",
    ),
    path("quiz/ai-generate/quiz/", ai_generate_quiz_view, name="ai_generate_quiz"),
    path("quiz/ai-generate/save/", ai_save_quiz_view, name="ai_save_quiz"),
    re_path(
        r"^static/(?P<path>.*)$",
        serve,
        {"document_root": settings.BASE_DIR / "main" / "static"},
    ),
]


def custom_404(request, exception):
    """Кастомная страница 404."""
    return render(request, "404.html", status=404)


handler404 = custom_404
