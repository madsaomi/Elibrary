from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def notification_badge(request):
    count = request.user.notifications.filter(is_read=False).count()
    return HttpResponse(f'<span id="notif-count">{count}</span>')


@login_required
def notification_list(request):
    from django.shortcuts import render
    notifs = request.user.notifications.all()[:5]
    return render(request, 'dashboard/notifications/_dropdown.html', {'notifications': notifs})


@login_required
def mark_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return HttpResponse('')
