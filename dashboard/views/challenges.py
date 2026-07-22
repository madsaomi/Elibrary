from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.gamification.models import Challenge, ChallengeAttempt


@login_required
def challenge_leaderboard(request):
    challenges = Challenge.objects.filter(status=Challenge.Status.PUBLISHED).order_by('-week_start')[:5]
    selected = None
    attempts = []
    user_rank = None
    user_attempt = None
    grade_numbers = []
    if request.GET.get('challenge_id'):
        selected = Challenge.objects.get(id=request.GET.get('challenge_id'))
        qs = ChallengeAttempt.objects.filter(challenge=selected, is_completed=True).select_related('user', 'user__grade').order_by('-score')
        if request.user.role == 'school_admin':
            qs = qs.filter(user__school=request.user.school)
        grade_param = request.GET.get('grade_number')
        if grade_param:
            qs = qs.filter(user__grade__number=int(grade_param))
        all_attempts = list(qs)
        attempts = all_attempts[:10]
        current = next((a for a in all_attempts if a.user_id == request.user.id), None)
        if current:
            user_rank = all_attempts.index(current) + 1
            if user_rank > 10:
                user_attempt = current
        grade_numbers = list(
            ChallengeAttempt.objects.filter(challenge=selected, is_completed=True)
            .values_list('user__grade__number', flat=True).distinct().order_by('user__grade__number')
        )
    return render(request, 'dashboard/challenges/leaderboard.html', {
        'challenges': challenges, 'selected': selected, 'attempts': attempts,
        'user_rank': user_rank, 'user_attempt': user_attempt, 'grade_numbers': grade_numbers,
    })


@login_required
def student_challenge(request):
    user = request.user
    if user.role != 'student':
        return redirect('dashboard:challenge_leaderboard')
    attempt = ChallengeAttempt.objects.filter(user=user, is_completed=False).order_by('-started_at').first()
    if attempt:
        return render(request, 'dashboard/challenges/take.html', {
            'questions': attempt.questions_data or attempt.challenge.questions,
            'attempt_id': str(attempt.id),
            'csrf_token': request.META.get('CSRF_COOKIE', ''),
        })
    active = Challenge.objects.filter(
        grade_number=user.grade.number if user.grade else None,
        status=Challenge.Status.PUBLISHED,
    ).order_by('-week_start').first()
    if active:
        return redirect('dashboard:student_challenge')
    return redirect('dashboard:challenge_leaderboard')


@login_required
def challenge_moderation(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    pending = Challenge.objects.filter(status=Challenge.Status.DRAFT)
    if request.user.role == 'school_admin':
        pending = pending.filter(Q(school=request.user.school) | Q(school__isnull=True))
    return render(request, 'dashboard/challenges/moderation.html', {'challenges': pending})


@login_required
def challenge_moderation_detail(request, challenge_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    challenge = Challenge.objects.get(id=challenge_id)
    if request.method == 'POST':
        import json as _json
        questions_raw = request.POST.get('questions')
        if questions_raw:
            challenge.questions = _json.loads(questions_raw)
        action = request.POST.get('action')
        if action == 'publish':
            challenge.status = Challenge.Status.PUBLISHED
        challenge.save()
        return redirect('dashboard:challenge_moderation')
    return render(request, 'dashboard/challenges/moderation_detail.html', {
        'challenge': challenge,
    })
