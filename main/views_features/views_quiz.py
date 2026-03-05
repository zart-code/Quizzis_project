import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from main.forms_features.forms_quiz import QuizForm
from main.models import Question, Answer


@login_required
def create_quiz_view(request):
    """
    Страница создания квиза.

    Квиз создаётся в два этапа:
    1. Сначала заполняется основная информация о квизе (название,
       имя создателя, доп. информация и т.д.) и сохраняется.
    2. Затем через динамическую форму добавляются вопросы
       с вариантами ответов (POST-запросы обрабатываются
       с помощью ручного парсинга данных из request.POST).
    """
    if request.method == 'POST':
        quiz_form = QuizForm(request.POST, user=request.user)

        if quiz_form.is_valid():
            quiz = quiz_form.save()

            # Парсим вопросы и ответы из POST-данных
            questions_saved = _save_questions_from_post(request.POST, quiz)

            if questions_saved == 0:
                messages.warning(
                    request,
                    'Квиз сохранён, но не добавлено ни одного вопроса. '
                    'Вы можете отредактировать его позже.',
                )
            else:
                messages.success(
                    request,
                    f'Квиз «{quiz.title}» успешно создан '
                    f'с {questions_saved} вопрос(ами)!',
                )

            return redirect('main_page')
        else:
            # Собираем данные вопросов обратно для отображения
            questions_data = _collect_questions_from_post(request.POST)
            return render(request, 'create_quiz.html', {
                'quiz_form': quiz_form,
                'questions_data': json.dumps(
                    questions_data, ensure_ascii=False,
                ),
            })
    else:
        quiz_form = QuizForm(user=request.user)

    return render(request, 'create_quiz.html', {
        'quiz_form': quiz_form,
        'questions_data': '[]',
    })


def _save_questions_from_post(post_data, quiz):
    """
    Извлекает вопросы и ответы из POST-данных и сохраняет
    их в базу данных.

    Ожидаемый формат ключей в POST:
        question_<N>_text       — текст вопроса
        question_<N>_type       — тип (single / multiple)
        question_<N>_answer_<M>_text    — текст ответа
        question_<N>_answer_<M>_correct — флаг правильности

    Возвращает количество сохранённых вопросов.
    """
    question_indices = _get_question_indices(post_data)
    saved_count = 0

    for order, q_idx in enumerate(sorted(question_indices), start=1):
        q_text = post_data.get(f'question_{q_idx}_text', '').strip()
        q_type = post_data.get(f'question_{q_idx}_type', 'single')

        if not q_text:
            continue

        question = Question.objects.create(
            quiz=quiz,
            text=q_text,
            question_type=q_type,
            order=order,
        )

        answer_indices = _get_answer_indices(post_data, q_idx)
        for a_idx in sorted(answer_indices):
            a_text_key = f'question_{q_idx}_answer_{a_idx}_text'
            a_correct_key = f'question_{q_idx}_answer_{a_idx}_correct'

            a_text = post_data.get(a_text_key, '').strip()
            if not a_text:
                continue

            Answer.objects.create(
                question=question,
                text=a_text,
                is_correct=(a_correct_key in post_data),
            )

        saved_count += 1

    return saved_count


def _collect_questions_from_post(post_data):
    """
    Собирает данные вопросов из POST для повторного отображения
    в шаблоне (при ошибке валидации формы квиза).
    """
    questions = []
    question_indices = _get_question_indices(post_data)

    for q_idx in sorted(question_indices):
        q_text = post_data.get(f'question_{q_idx}_text', '')
        q_type = post_data.get(f'question_{q_idx}_type', 'single')

        answers = []
        answer_indices = _get_answer_indices(post_data, q_idx)
        for a_idx in sorted(answer_indices):
            a_text = post_data.get(
                f'question_{q_idx}_answer_{a_idx}_text', '',
            )
            a_correct = (
                f'question_{q_idx}_answer_{a_idx}_correct' in post_data
            )
            answers.append({
                'text': a_text,
                'is_correct': a_correct,
            })

        questions.append({
            'text': q_text,
            'type': q_type,
            'answers': answers,
        })

    return questions


def _get_question_indices(post_data):
    """Извлекает уникальные индексы вопросов из ключей POST."""
    indices = set()
    for key in post_data:
        if key.startswith('question_') and '_text' in key:
            parts = key.split('_')
            if len(parts) >= 3 and parts[1].isdigit():
                # question_N_text (не question_N_answer_M_text)
                if parts[2] == 'text':
                    indices.add(int(parts[1]))
    return indices


def _get_answer_indices(post_data, question_idx):
    """Извлекает уникальные индексы ответов для вопроса."""
    indices = set()
    prefix = f'question_{question_idx}_answer_'
    for key in post_data:
        if key.startswith(prefix):
            rest = key[len(prefix):]
            parts = rest.split('_')
            if len(parts) >= 1 and parts[0].isdigit():
                indices.add(int(parts[0]))
    return indices
