from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from main.models import Quiz, Question, Answer


@login_required
def create_quiz_view(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        quiz = Quiz.objects.create(title=title, creator=request.user)

        i = 1
        while request.POST.get(f'q{i}_text'):
            q = Question.objects.create(
                quiz=quiz,
                text=request.POST.get(f'q{i}_text'),
                order=i,
            )
            correct = request.POST.get(f'q{i}_correct')
            for j in range(4):
                Answer.objects.create(
                    question=q,
                    text=request.POST.get(f'q{i}_ans{j}', ''),
                    is_correct=(str(j) == correct),
                )
            i += 1

        return redirect('main_page')

    return render(request, 'create_quiz.html')
