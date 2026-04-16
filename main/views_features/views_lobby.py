"""Views для лобби"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from main.models import GameSession, Quiz, GameParticipant, GameAnswer


@login_required
def create_lobby_view(request, quiz_id):
    """Создание квиза/лобби"""
    print(quiz_id)
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)
    print(quiz)
    session = GameSession.objects.create(quiz=quiz, host=request.user)
    print(session)
    session.save()
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
            'role': getattr(p.user, 'profile', None)
                    and p.user.profile.role or 'ученик',
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
    print(request, pin)
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    if session.participants.count() == 0:
        return redirect('lobby', pin=pin)
    session.status = GameSession.IN_PROGRESS
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

    # Показать результаты если игра завершена или вопросы кончились
    if session.status == GameSession.FINISHED or session.current_question >= total:
        return render(request, 'session_results.html', {
            'session': session,
            'participant': participant,
        })

    if session.status != GameSession.IN_PROGRESS:
        return redirect('join_lobby', pin=pin)

    question = questions[session.current_question]

    if request.method == 'POST':
        if not participant.is_answered:
            timed_out = request.POST.get('timed_out') == '1'
            is_correct = False

            if not timed_out:
                if question.question_type == 'single':
                    chosen_id = request.POST.get('answer')
                    correct = question.answers.filter(is_correct=True).first()
                    is_correct = (
                        bool(chosen_id)
                        and correct is not None
                        and str(correct.id) == chosen_id
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

            if is_correct:
                participant.score += 1
            participant.is_answered = True
            participant.save()

            GameAnswer.objects.get_or_create(
                session=session,
                participant=participant,
                question=question,
                defaults={'is_correct': is_correct},
            )

            total_participants = session.participants.count()
            answered = session.participants.filter(is_answered=True).count()
            if answered >= total_participants:
                session.participants.update(is_answered=False)
                session.current_question += 1
                if session.current_question >= total:
                    session.status = GameSession.FINISHED
                session.save()

        return redirect('session_play', pin=pin)

    return render(request, 'session_play.html', {
        'session': session,
        'question': question,
        'participant': participant,
        'index': session.current_question,
        'total': total,
        'answered': participant.is_answered,
    })


