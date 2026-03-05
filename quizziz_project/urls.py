from django.contrib import admin
from django.urls import path
from main.views import *

"""
Структура страниц в формате x.y (где x - уровень, y - номер страницы на этом уровне):

Уровень 0 - Главная
0.1 - Главная страница (меню) main_page

Уровень 1 - Аутентификация
1.1 - Страница входа login_page
1.2 - Страница регистрации register_page
1.3 - Страница выхода logout (редирект на main_page)

Уровень 2 - Профиль пользователя
2.1 - Страница профиля profile
2.2 - Редактирование профиля edit_profile
"""

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', main_page, name='main_page'),
    path('login/', login_page, name='login_page'),
    path('register/', register_page, name='register_page'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', edit_profile_view, name='edit_profile'),
    path('quiz/create/', create_quiz_view, name='create_quiz'),
]
