from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Notification
from .services import mark_all_read_for_user, mark_notification_read


@login_required
def center(request):
    notifications = (
        Notification.objects.filter(user=request.user)
        .order_by('-created_at')
    )
    paginator = Paginator(notifications, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'notifications/center.html', {'page_obj': page_obj})


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    mark_notification_read(notification)
    return redirect(request.POST.get('next') or 'notifications:center')


@login_required
@require_POST
def mark_all_read(request):
    mark_all_read_for_user(request.user)
    return redirect(request.POST.get('next') or 'notifications:center')


@login_required
def go(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    mark_notification_read(notification)
    target = notification.link_url.strip() if notification.link_url else ''
    if target.startswith('/'):
        return redirect(target)
    return redirect('notifications:center')

