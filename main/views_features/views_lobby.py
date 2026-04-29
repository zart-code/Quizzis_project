"""Views для лобби"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from main.models import GameSession, Quiz, GameParticipant, GameAnswer, Question, QuizResult
from django.utils import timezone


@login_required
def create_lobby_view(request, quiz_id):
    """Создание квиза/лобби"""
    print(quiz_id)
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)

    if quiz.status == Quiz.DRAFT:
        return redirect('my_quizzes')

    session = GameSession.objects.create(quiz=quiz, host=request.user)
    return redirect('lobby', pin=session.pin)


@login_required
def lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    return render(request, 'lobby.html', {'session': session})


@login_required
@require_POST
def toggle_lock_view(request, pin):
    """Закрытие/открытие возможности присоединиться к сессии"""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    session.is_locked = not session.is_locked
    session.save()
    return redirect('lobby', pin=pin)


@login_required
@require_POST
def delete_session_view(request, pin):
    """"""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    session.delete()
    return redirect('my_quizzes')


@login_required
def api_players_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    participants = session.participants.select_related('user').all()

    players = [
        {
            'username': p.user.username,

        }
        for p in participants
    ]

    return JsonResponse({
        'players': players,
        'count': len(players),
        'is_locked': session.is_locked,
    })


@login_required
def join_lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)

    if session.host == request.user:
        return redirect('lobby', pin=pin)

    if session.status != GameSession.WAITING:
        return render(request, 'lobby_error.html', {'message': 'Игра уже началась или завершена.'})

    if session.is_locked:
        return render(request, 'lobby_error.html', {'message': 'Лобби закрыто для новых игроков.'})

    if session.participants.count() >= 25:
        return render(request, 'lobby_error.html', {'message': 'Лобби заполнено (максимум 25 игроков).'})

    from main.models import GameParticipant
    GameParticipant.objects.get_or_create(session=session, user=request.user)

    return render(request, 'join_lobby.html', {'session': session})


@login_required
@require_POST
def start_game_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    if session.participants.count() == 0:
        return redirect('lobby', pin=pin)
    session.status = GameSession.IN_PROGRESS
    session.current_question_started_at = timezone.now()
    session.save()
    return redirect('lobby', pin=pin)


@login_required
def api_state_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    return JsonResponse({
        'status': session.status,
    })


@login_required
def session_play_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin)
    participant = get_object_or_404(
        GameParticipant, session=session, user=request.user
    )
    questions = list(session.quiz.questions.prefetch_related('answers').all())
    total = len(questions)
    total_max_score = sum(
        4 * q.coefficient for q in questions
    )
    # Показать результаты если игра завершена или вопросы кончились
    if session.status == GameSession.FINISHED or session.current_question >= total:
        result_session_key = f'lobby_result_{pin}'
        result_id = request.session.get(result_session_key)
        score_percent = (participant.score / total_max_score * 100) if total_max_score else 0

        if result_id is not None:
            QuizResult.objects.filter(id=result_id, user=request.user).update(
                score=participant.score,
                max_score=total_max_score,
                score_percent=score_percent,
                completed=True,
                completed_at=timezone.now(),
            )

        return render(request, 'session_results.html', {
            'session': session,
            'participant': participant,
        })

    if session.status != GameSession.IN_PROGRESS:
        return redirect('join_lobby', pin=pin)

    result_session_key = f'lobby_result_{pin}'
    result_id = request.session.get(result_session_key)

    if result_id is None:
        result = QuizResult.objects.create(
            user=request.user,
            quiz=session.quiz,
            score=0,
            max_score=total_max_score,
            score_percent=0,
            completed=False,
        )
        request.session[result_session_key] = result.id
    question = questions[session.current_question]
    question_started_at = session.current_question_started_at or timezone.now()
    elapsed_seconds = int((timezone.now() - question_started_at).total_seconds())
    remaining_seconds = max(0, question.time_limit - elapsed_seconds)
    server_timed_out = remaining_seconds <= 0
    if request.method == 'POST':
        if not participant.is_answered:
            timed_out = request.POST.get('timed_out') == '1' or server_timed_out
            k = question.coefficient
            max_points = 4 * k
            earned_points = 0
            is_correct = False

            if not timed_out:
                if question.question_type == 'single':
                    chosen_id = request.POST.get('answer')
                    answers = list(question.answers.all())
                    correct_answer = next((a for a in answers if a.is_correct), None)

                    if correct_answer and str(correct_answer.id) == chosen_id:
                        earned_points += 4 * k

                    is_correct = earned_points == max_points

                elif question.question_type == 'multiple':
                    chosen_ids = set(request.POST.getlist('answer'))
                    answers = list(question.answers.all())

                    mistakes = 0
                    for answer in answers:
                        user_marked = str(answer.id) in chosen_ids
                        if user_marked != answer.is_correct:
                            mistakes += 1

                    if mistakes == 0:
                        earned_points = 4 * k
                    elif mistakes == 1:
                        earned_points = 2 * k
                    elif mistakes == 2:
                        earned_points = 1 * k
                    else:
                        earned_points = 0

                    is_correct = mistakes == 0

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

            participant.score += earned_points
            participant.is_answered = True
            participant.save()

            GameAnswer.objects.get_or_create(
                session=session,
                participant=participant,
                question=question,
                defaults={
                    'is_correct': is_correct,
                    'points': earned_points,
                },
            )

            total_participants = session.participants.count()
            answered = session.participants.filter(is_answered=True).count()
            if answered >= total_participants:
                session.participants.update(is_answered=False)
                session.current_question += 1
                if session.current_question >= total:
                    session.status = GameSession.FINISHED
                    session.current_question_started_at = None
                else:
                    session.current_question_started_at = timezone.now()
                session.save()

        return redirect('session_play', pin=pin)

    response = render(request, 'session_play.html', {
        'session': session,
        'question': question,
        'participant': participant,
        'index': session.current_question,
        'total': total,
        'answered': participant.is_answered,
        'remaining_seconds': remaining_seconds,
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response




@login_required
def quiz_sessions_list_view(request, quiz_id):
    """Список всех сессий квиза для учителя (история прохождений)"""
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)
    sessions = quiz.sessions.all().order_by('-created_at')
    return render(request, 'quiz_sessions_list.html', {
        'quiz': quiz,
        'sessions': sessions,
    })


@login_required
def session_results_teacher_view(request, pin):
    """Детальные результаты сессии для учителя: таблица участник × вопрос"""
    session = get_object_or_404(GameSession, pin=pin, host=request.user)

    # Questions in order
    questions = list(session.quiz.questions.all())

    # Participants sorted by score descending (rank 1 = best)
    participants = list(
        session.participants.select_related('user').order_by('-score')
    )

    # Build answers lookup: {participant_id: {question_id: is_correct}}
    answers_qs = GameAnswer.objects.filter(session=session).values(
        'participant_id', 'question_id', 'is_correct', 'points'
    )
    answers_map = {}
    for ga in answers_qs:
        answers_map.setdefault(ga['participant_id'], {})[ga['question_id']] = {
            'is_correct': ga['is_correct'],
            'points': ga['points'],
        }

    # Build rows for template
    rows = []
    for rank, p in enumerate(participants, 1):
        q_results = []
        for q in questions:
            val = answers_map.get(p.id, {}).get(q.id, None)
            if val is None:
                q_results.append(None)
            else:
                q_results.append({
                    'points': val['points'],
                    'max_points': 4 * q.coefficient,
                    'is_correct': val['is_correct'],
                })
        rows.append({
            'rank': rank,
            'user': p.user,
            'score': p.score,
            'max_score': sum(4 * q.coefficient for q in questions),
            'q_results': q_results,
        })

    return render(request, 'session_results_teacher.html', {
        'session': session,
        'questions': questions,
        'rows': rows,
    })
