from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.notifications.models import News
from apps.notifications.services import NewsService


@login_required
def news_list(request):
    news = NewsService.visible_to(request.user)
    return render(request, 'dashboard/news/list.html', {'news': news})


@login_required
def news_create(request):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if title and content:
            News.objects.create(
                title=title, content=content,
                author=request.user,
                author_level=News.AuthorLevel.SUPERADMIN if request.user.role == 'superadmin' else News.AuthorLevel.SCHOOL_ADMIN,
                school=None if request.user.role == 'superadmin' else request.user.school,
                is_published=request.POST.get('is_published') == '1',
                published_at=timezone.now() if request.POST.get('is_published') == '1' else None,
            )
        return redirect('dashboard:news_list')
    return render(request, 'dashboard/news/create.html')
