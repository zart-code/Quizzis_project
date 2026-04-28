"""Views для квизов"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from main.models import Quiz, Question, Answer, Profile,QuizResult
from django.views.decorators.http import require_POST
from django.utils import timezone


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
    total_questions = 0
    for quiz in quizzes:
        total_questions += quiz.total_questions()
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
            score = sum(r['points'] for r in answers_log)
            total = sum(r['max_points'] for r in answers_log)
            score_percent = (score / total * 100) if total else 0

            result_id = request.session.get(f'quiz_{quiz_id}_result_id')
            if result_id:
                QuizResult.objects.filter(
                    id=result_id,
                    user=request.user,
                    quiz=quiz
                ).update(
                    score=score,
                    max_score=total,
                    score_percent=score_percent,
                    completed=True,
                    completed_at=timezone.now(),
                )

            request.session.pop(f'quiz_{quiz_id}_log', None)
            request.session.pop(f'quiz_{quiz_id}_index', None)
            request.session.pop(f'quiz_{quiz_id}_result_id', None)

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
            k = question.coefficient
            max_points = 4 * k
            earned_points = 0
            is_correct = False
            correct_answer = None

            if not timed_out:
                if question.question_type == 'single':
                    chosen_id = request.POST.get('answer')
                    answers = list(question.answers.all())
                    correct_answer = next((a for a in answers if a.is_correct), None)

                    for answer in answers:
                        user_marked = str(answer.id) == chosen_id
                        if user_marked == answer.is_correct:
                            earned_points += k

                    is_correct = earned_points == max_points

                elif question.question_type == 'multiple':
                    chosen_ids = set(request.POST.getlist('answer'))
                    answers = list(question.answers.all())

                    for answer in answers:
                        user_marked = str(answer.id) in chosen_ids
                        if user_marked == answer.is_correct:
                            earned_points += k

                    is_correct = earned_points == max_points

                elif question.question_type == 'number':
                    raw = request.POST.get('answer_number', '')
                    try:
                        if float(raw) == question.correct_number:
                            earned_points = max_points
                    except ValueError:
                        earned_points = 0

                    is_correct = earned_points == max_points

                elif question.question_type == 'text':
                    is_correct = None
                    max_points = 0
                    earned_points = 0

            log = request.session.get(f'quiz_{quiz_id}_log', [])
            log.append({
                'points': earned_points,
                'max_points': max_points,
                'correct': is_correct,
            })
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
                'earned_points': earned_points,
                'question_max_points': max_points,
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

    result = QuizResult.objects.create(
        user=request.user,
        quiz=quiz,
        score=0,
        max_score=len(questions),
        score_percent=0,
        completed=False,
    )

    request.session[f'quiz_{quiz_id}_log'] = []
    request.session[f'quiz_{quiz_id}_index'] = 0
    request.session[f'quiz_{quiz_id}_result_id'] = result.id
    return render(request, 'play_quiz.html', {
        'quiz': quiz,
        'question': questions[0],
        'index': 0,
        'total': len(questions),
        'finished': False,
        'show_result': False,
    })
