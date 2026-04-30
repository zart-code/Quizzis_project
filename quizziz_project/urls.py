"""
Главный файл url проекта
------------------------
Уровень 0 — Главная
  0.1 - Главная страница (меню) [main_page] /

Уровень 1 — Аутентификация
  1.1 - Вход [login_page] /login/
  1.2 - Регистрация [register_page] /register/
  1.3 - Выход [logout] /logout/ (редирект на 0.1)

Уровень 2 — Профиль
  2.1 - Профиль [profile] /profile/
  2.2 - Редактирование профиля [edit_profile] /profile/edit/

Уровень 3 — Квизы
  3.1 - Мои квизы [my_quizzes] /my-quizzes/
  3.2 - Создание квиза [create_quiz] /quiz/create/
        → после создания редирект на 4.1 (создание лобби)
  3.3 - Одиночное прохождение квиза [play_quiz] /quiz/<id>/play/

Уровень 4 — Лобби (хост)
  4.1 - Создание лобби [create_lobby] /quiz/<id>/lobby/create/
        → редирект на 4.2
  4.2 - Лобби хоста [lobby] /lobby/<pin>/
  4.3 - Закрыть/открыть лобби [toggle_lock] /lobby/<pin>/lock/ (редирект на 4.2)
  4.4 - Удалить сессию [delete_session] /lobby/<pin>/delete/ (редирект на 3.1)
  4.5 - Начать игру [start_game] /lobby/<pin>/start/ (редирект на 4.2)

Уровень 5 — Подключение игрока
  5.1 - Подключение по PIN [join_lobby] /join/<pin>/
        → страница ожидания старта

Уровень 6 — Синхронная игра
  6.1 - Прохождение квиза игроком [session_play] /session/<pin>/play/
        → после последнего вопроса: страница результатов

Уровень 7 — API (служебные, без шаблонов)
  7.1 - Список игроков в лобби [api_players] /lobby/<pin>/api/players/
  7.2 - Статус сессии [api_state] /session/<pin>/api/state/
        → используется polling'ом на 5.1 и 6.1
"""


from django.contrib import admin
from django.urls import path
from main.views import *
from main.views_features.views_profile import *
from main.views_features.views_quiz import *
from main.views_features.views_lobby import *
from main.views_features.views_admin import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', main_page, name='main_page'),
    path('login/', login_page, name='login_page'),
    path('register/', register_page, name='register_page'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('profile/history/', profile_history_view, name='profile_history'),
    path('profile/edit/', edit_profile_view, name='edit_profile'),
    path('quiz/create/', create_quiz_view, name='create_quiz'),
    path('my-quizzes/', my_quizzes_view, name='my_quizzes'),
    path('quiz/<int:quiz_id>/toggle-status/', toggle_quiz_status_view, name='toggle_quiz_status'),
    path('quiz/<int:quiz_id>/play/', play_quiz_view, name='play_quiz'),
    path('quiz/<int:quiz_id>/lobby/create/', create_lobby_view, name='create_lobby'),
    path('lobby/<str:pin>/', lobby_view, name='lobby'),
    path('lobby/<str:pin>/lock/', toggle_lock_view, name='toggle_lock'),
    path('lobby/<str:pin>/delete/', delete_session_view, name='delete_session'),
    path('lobby/<str:pin>/api/players/', api_players_view, name='api_players'),
    path('join/<str:pin>/', join_lobby_view, name='join_lobby'),
    path('lobby/<str:pin>/start/', start_game_view, name='start_game'),
    path('session/<str:pin>/api/state/', api_state_view, name='api_state'),
    path('session/<str:pin>/play/', session_play_view, name='session_play'),
    path('quiz/<int:quiz_id>/sessions/', quiz_sessions_list_view, name='quiz_sessions_list'),
    path('session/<str:pin>/results/teacher/', session_results_teacher_view, name='session_results_teacher'),
    path('quizzises/', quizzes_view, name='quizzes_view'),
    path('admin-panel/', admin_panel_view, name='admin_panel'),
    path('admin-panel/ban/<int:user_id>/', admin_ban_user_view, name='admin_ban_user'),
    path('admin-panel/unpublish-quiz/<int:quiz_id>/',
         admin_unpublish_quiz_view,
         name='admin_unpublish_quiz'),
    path('admin-panel/delete-quiz/<int:quiz_id>/',
         admin_delete_quiz_view,
         name='admin_delete_quiz'),
    path('admin-panel/user/<int:user_id>/', profile_view, name='admin_user_profile'),
    path('admin-panel/user/<int:user_id>/history/', profile_history_view, name='admin_user_history'),
    path('admin-panel/user/<int:user_id>/edit/', edit_profile_view, name='admin_edit_user'),
    path('admin-panel/api/stats/', api_admin_stats_view, name='api_admin_stats'),
    path('admin-panel/api/users/', api_admin_users_view, name='api_admin_users'),
    path('admin-panel/api/quizzes/', api_admin_quizzes_view, name='api_admin_quizzes'),
]