from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from . import centre
from .models import Notification
from .services import mark_all_read_for_user, mark_notification_read


@login_required
def center(request):
    """Reading it marks it read.

    Every row used to carry its own *Mark read* form — a chore the page
    invented for itself. Opening the tab clears what is on screen, one honest
    "Mark all read" sits at the top, and the row's only button is the thing
    it is about.
    """
    everything = Notification.objects.filter(user=request.user).order_by('-created_at')
    which = request.GET.get('show', '')

    paginator = Paginator(centre.apply_filter(everything, which), 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Count before marking, or the page would report zero unread the moment
    # it explains that three of them want something from you.
    on_screen = list(page_obj)
    unread_here = [note for note in on_screen if not note.is_read]
    wants_you = sum(
        1 for note in unread_here
        if centre.tone_for(note.notification_type) in ('urgent', 'answer')
    )

    context = {
        'days': centre.rows(on_screen),
        'page_obj': page_obj,
        'chips': centre.chips(everything, which),
        'which': which,
        'unread_here': len(unread_here),
        'wants_you': wants_you,
        'unread_total': everything.filter(is_read=False).count(),
    }

    # Seen is read. Done after the counts so the page describes what the
    # collector is actually looking at, not what is left afterwards.
    if unread_here:
        Notification.objects.filter(
            pk__in=[note.pk for note in unread_here]
        ).update(is_read=True)

    return render(request, 'notifications/center.html', context)


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

