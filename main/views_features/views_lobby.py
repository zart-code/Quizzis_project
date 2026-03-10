import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from main.models import GameSession, Quiz


@login_required
def create_lobby_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, creator=request.user)
    session = GameSession.objects.create(quiz=quiz, host=request.user)
    return redirect('lobby', pin=session.pin)


@login_required
def lobby_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    return render(request, 'lobby.html', {'session': session})


@login_required
@require_POST
def toggle_lock_view(request, pin):
    session = get_object_or_404(GameSession, pin=pin, host=request.user)
    session.is_locked = not session.is_locked
    session.save()
    return redirect('lobby', pin=pin)


@login_required
@require_POST
def delete_session_view(request, pin):
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
