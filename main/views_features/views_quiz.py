from django.shortcuts import render, redirect, get_object_or_404
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

        return redirect('my_quizzes')

    return render(request, 'create_quiz.html')


@login_required
def my_quizzes_view(request):
    quizzes = Quiz.objects.filter(creator=request.user).order_by('-created_at')
    return render(request, 'my_quizzes.html', {'quizzes': quizzes})


@login_required
def play_quiz_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.prefetch_related('answers').all()

    if request.method == 'POST':
        score = 0
        total = questions.count()
        for question in questions:
            chosen = request.POST.get(f'q{question.id}')
            correct = question.answers.filter(is_correct=True).first()
            if correct and str(correct.id) == chosen:
                score += 1
        return render(request, 'play_quiz.html', {
            'quiz': quiz,
            'questions': questions,
            'score': score,
            'total': total,
            'finished': True,
        })

    return render(request, 'play_quiz.html', {
        'quiz': quiz,
        'questions': questions,
        'finished': False,
    })
