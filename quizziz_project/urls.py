from django.contrib import admin
from django.urls import path
from main.views import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', main_page, name='main_page'),
    path('login/', login_page, name='login_page'),
    path('register/', register_page, name='register_page'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', edit_profile_view, name='edit_profile'),
    path('quiz/create/', create_quiz_view, name='create_quiz'),
    path('my-quizzes/', my_quizzes_view, name='my_quizzes'),
    path('quiz/<int:quiz_id>/play/', play_quiz_view, name='play_quiz'),
    path('quiz/<int:quiz_id>/lobby/create/', create_lobby_view, name='create_lobby'),
    path('lobby/<str:pin>/', lobby_view, name='lobby'),
    path('lobby/<str:pin>/lock/', toggle_lock_view, name='toggle_lock'),
    path('lobby/<str:pin>/delete/', delete_session_view, name='delete_session'),
    path('lobby/<str:pin>/api/players/', api_players_view, name='api_players'),
    path('join/<str:pin>/', join_lobby_view, name='join_lobby'),
]
