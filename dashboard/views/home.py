from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.models import User
from apps.gamification.models import UserLevel
from apps.notifications.services import NewsService
from apps.schools.models import School, District
from dashboard.services import get_school_stats


@login_required
def home(request):
    stats = {}
    news = []
    leaderboard = []
    user_rank = None
    user_entry = None
    if request.user.role == 'superadmin':
        schools_count = School.objects.count()
        districts_count = District.objects.count()
        total_students = User.objects.filter(role=User.Role.STUDENT).count()
    elif request.user.school:
        stats = get_school_stats(request.user.school)
        news = NewsService.visible_to(request.user)[:5]
        full_lb = list(UserLevel.objects.filter(
            user__school=request.user.school,
        ).select_related('user', 'level').order_by('-total_xp'))
        leaderboard = full_lb[:10]
        current = next((ul for ul in full_lb if ul.user_id == request.user.id), None)
        if current:
            user_rank = full_lb.index(current) + 1
            if user_rank > 10:
                user_entry = current
    return render(request, 'dashboard/home.html', {
        'stats': stats,
        'news': news,
        'leaderboard': leaderboard,
        'user_rank': user_rank,
        'user_entry': user_entry,
    })
