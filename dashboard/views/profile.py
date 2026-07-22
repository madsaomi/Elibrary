from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.gamification.services import award_freeze_days


@login_required
def profile(request):
    from apps.gamification.models import Achievement as AchModel
    streak = getattr(request.user, 'streak', None)
    level_info = getattr(request.user, 'level_info', None)
    ctx = {'streak': streak, 'level_info': level_info}
    if request.user.role == 'student':
        achievements = request.user.achievements.select_related('achievement').all()
        ctx['earned_ids'] = set(ua.achievement_id for ua in achievements)
        ctx['all_achievements'] = AchModel.objects.all()
    from django.shortcuts import render
    return render(request, 'dashboard/profile.html', ctx)


@login_required
@require_POST
def award_freeze_view(request, user_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        from django.shortcuts import render
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    target = User.objects.get(id=user_id)
    if target.school != request.user.school:
        from django.shortcuts import render
        return render(request, 'dashboard/error.html', {'error': _('Пользователь из другой школы')})
    days = int(request.POST.get('days', 1))
    award_freeze_days(target, days)
    return redirect('dashboard:profile')


@login_required
def edit_profile(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        if first_name and last_name:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
    return redirect('dashboard:profile')


@login_required
def change_password(request):
    if request.method == 'POST':
        old = request.POST.get('old_password', '')
        new = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not request.user.check_password(old):
            return redirect('dashboard:profile')
        if len(new) < 6:
            return redirect('dashboard:profile')
        if new != confirm:
            return redirect('dashboard:profile')
        request.user.set_password(new)
        request.user.save()
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        return redirect('dashboard:profile')
    return redirect('dashboard:profile')
