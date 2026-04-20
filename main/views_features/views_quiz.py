"""Views для квизов"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from main.models import Quiz, Question, Answer, Profile
from django.views.decorators.http import require_POST


@login_required
def create_quiz_view(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_banned:
        return render(request, 'banned_create_quiz.html')
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        messages.error(request, 'Создавать квизы могут только учителя и администраторы.')
        return redirect('main_page')

    if request.method == 'POST':
        title = request.POST.get('title')
        quiz = Quiz.objects.create(
            title=title,
            creator=request.user,
            status = Quiz.DRAFT
        )

        i = 1
        while request.POST.get(f'q{i}_text'):
            q_type = request.POST.get(f'q{i}_type', 'single')
            time_limit = int(request.POST.get(f'q{i}_time', 30))

            q = Question.objects.create(
                quiz=quiz,
                text=request.POST.get(f'q{i}_text'),
                question_type=q_type,
                order=i,
                time_limit=time_limit,
            )

            if q_type == 'single':
                correct = request.POST.get(f'q{i}_correct')
                for j in range(4):
                    Answer.objects.create(
                        question=q,
                        text=request.POST.get(f'q{i}_ans{j}', ''),
                        is_correct=(str(j) == correct),
                    )

            elif q_type == 'multiple':
                correct_list = request.POST.getlist(f'q{i}_correct')
                for j in range(4):
                    Answer.objects.create(
                        question=q,
                        text=request.POST.get(f'q{i}_ans{j}', ''),
                        is_correct=(str(j) in correct_list),
                    )

            elif q_type == 'number':
                raw = request.POST.get(f'q{i}_correct_number', '0')
                try:
                    q.correct_number = float(raw)
                except ValueError:
                    q.correct_number = 0
                q.save()

            # text — ответ не сохраняем, проверка вручную

            i += 1

        return redirect('my_quizzes')

    return render(request, 'create_quiz.html')


@login_required
def my_quizzes_view(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role not in [Profile.ADMIN, Profile.TEACHER]:
        messages.error(request, 'Раздел "Мои квизы" доступен только учителям и администраторам.')
        return redirect('main_page')

    quizzes = Quiz.objects.filter(creator=request.user).order_by('-created_at')
    total_questions = Question.objects.filter(quiz__creator=request.user).count()
    context = {
        'quizzes': quizzes,
        'total_questions': total_questions,
    }
    return render(request, 'my_quizzes.html', context)


@login_required
@require_POST
def toggle_quiz_status_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)

    if quiz.status == Quiz.DRAFT:
        quiz.status = Quiz.ACTIVE
    else:
        quiz.status = Quiz.DRAFT

    quiz.save()
    return redirect('my_quizzes')


@login_required
def play_quiz_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if quiz.status == Quiz.DRAFT and quiz.creator != request.user:
        return redirect('quizzes_view')

    questions = list(quiz.questions.prefetch_related('answers').all())

    if not questions:
        return redirect('my_quizzes')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'finish':
            answers_log = request.session.get(f'quiz_{quiz_id}_log', [])
            score = sum(1 for r in answers_log if r['correct'])
            total = len(answers_log)
            request.session.pop(f'quiz_{quiz_id}_log', None)
            request.session.pop(f'quiz_{quiz_id}_index', None)
            return render(request, 'play_quiz.html', {
                'quiz': quiz,
                'score': score,
                'total': total,
                'finished': True,
            })

        if action == 'answer':
            index = int(request.POST.get('index', 0))
            question = questions[index]
            timed_out = request.POST.get('timed_out') == '1'
            is_correct = False
            correct_answer = None

            if not timed_out:
                if question.question_type == 'single':
                    chosen_id = request.POST.get('answer')
                    correct_answer = question.answers.filter(is_correct=True).first()
                    is_correct = (
                        bool(chosen_id)
                        and correct_answer is not None
                        and str(correct_answer.id) == chosen_id
                    )

                elif question.question_type == 'multiple':
                    chosen_ids = set(request.POST.getlist('answer'))
                    correct_ids = set(
                        str(a.id) for a in question.answers.filter(is_correct=True)
                    )
                    is_correct = chosen_ids == correct_ids

                elif question.question_type == 'number':
                    raw = request.POST.get('answer_number', '')
                    try:
                        is_correct = float(raw) == question.correct_number
                    except ValueError:
                        is_correct = False

                elif question.question_type == 'text':
                    is_correct = None  # проверяется вручную

            log = request.session.get(f'quiz_{quiz_id}_log', [])
            log.append({'correct': bool(is_correct)})
            request.session[f'quiz_{quiz_id}_log'] = log

            next_index = index + 1
            is_last = next_index >= len(questions)

            return render(request, 'play_quiz.html', {
                'quiz': quiz,
                'question': question,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'timed_out': timed_out,
                'next_index': next_index,
                'is_last': is_last,
                'finished': False,
                'show_result': True,
            })

        if action == 'next':
            index = int(request.POST.get('index', 0))
            question = questions[index]
            return render(request, 'play_quiz.html', {
                'quiz': quiz,
                'question': question,
                'index': index,
                'total': len(questions),
                'finished': False,
                'show_result': False,
            })

    request.session[f'quiz_{quiz_id}_log'] = []
    request.session[f'quiz_{quiz_id}_index'] = 0
    return render(request, 'play_quiz.html', {
        'quiz': quiz,
        'question': questions[0],
        'index': 0,
        'total': len(questions),
        'finished': False,
        'show_result': False,
    })
