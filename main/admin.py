from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    CustomUser, Achievement, UserAchievement,
    Category, Quizz, Question, Answer,
)

# ---- Кастомный пользователь ----
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'total_points', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'bio', 'avatar', 'date_of_birth')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Game stats'), {'fields': ('total_points',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'first_name', 'last_name'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)

# ---- Достижения ----
@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('name', 'points', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('points',)

# ---- Связь пользователей с достижениями ----
@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'earned_at')
    list_filter = ('earned_at', 'achievement')
    search_fields = ('user__username', 'achievement__name')
    raw_id_fields = ('user', 'achievement')  # для больших списков

# ---- Категории викторин ----
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# ---- Викторины ----
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True

@admin.register(Quizz)
class QuizzAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'is_published', 'created_at')
    list_filter = ('is_published', 'category', 'created_at')
    search_fields = ('title', 'description')
    raw_id_fields = ('created_by',)
    inlines = [QuestionInline]
    fieldsets = (
        (None, {'fields': ('title', 'description', 'category', 'created_by')}),
        ('Настройки', {'fields': ('is_published', 'time_limit', 'pass_score')}),
    )

# ---- Вопросы ----
class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    fields = ('text', 'is_correct', 'order')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text_short', 'quizz', 'question_type', 'points', 'order')
    list_filter = ('question_type', 'quizz__category')
    search_fields = ('text',)
    raw_id_fields = ('quizz',)
    inlines = [AnswerInline]

    def text_short(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_short.short_description = 'Текст вопроса'

# ---- Варианты ответов ----
@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct', 'order')
    list_filter = ('is_correct', 'question__quizz')
    search_fields = ('text', 'question__text')
    raw_id_fields = ('question',)

