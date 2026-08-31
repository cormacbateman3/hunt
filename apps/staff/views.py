"""The staff desk — Pass 11, first rooms.

The 17a/19b drawings, built against what is queryable today: a desk of
true counts, and the moderation room the drawings predate — the watcher
(Pass 9f) stores the classifier's 0–1 category scores and Claude's
in-context read on every scan, and this is where a human finally gets
to SEE them. The house rule holds here harder than anywhere: the system
only finds, these screens are where somebody decides.

Django admin stays exactly as it is for editing rows; the desk links
into it for everything that is already the right shape there.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages as flash
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import ReferenceDataSuggestion
from apps.listings.models import ListingQuestion
from apps.messaging.models import Message, MessageReport
from apps.moderation.models import MessageScan, ModerationEvent, ModerationSettings
from apps.orders.models import Order


def _config():
    """The tunables singleton — unsaved defaults when nobody has edited it."""
    return ModerationSettings.objects.first() or ModerationSettings()


@staff_member_required
def desk(request):
    """Six true counts, ordered by what breaks first, and the urgent list."""
    open_events = ModerationEvent.objects.filter(status='open')
    tiles = [
        {
            'count': open_events.filter(severity='urgent').count(),
            'label': 'Urgent moderation',
            'tone': 'rust',
            'url': '/staff/moderation/?show=urgent',
        },
        {
            'count': open_events.count(),
            'label': 'Moderation queue',
            'tone': 'ink',
            'url': '/staff/moderation/',
        },
        {
            'count': MessageReport.objects.filter(
                status__in=('open', 'reviewing')).count(),
            'label': 'Member reports',
            'tone': 'ink',
            'url': '/admin/messaging/messagereport/?status__exact=open',
        },
        {
            'count': ListingQuestion.objects.filter(
                moderation_state='flagged').count(),
            'label': 'Questions held',
            'tone': 'ink',
            'url': '/admin/listings/listingquestion/?moderation_state__exact=flagged',
        },
        {
            'count': Order.objects.filter(status='pending_payment').count(),
            'label': 'Payments open',
            'tone': 'ink',
            'url': '/admin/orders/order/?status__exact=pending_payment',
        },
        {
            'count': ReferenceDataSuggestion.objects.filter(
                status='pending').count(),
            'label': 'Suggestions pending',
            'tone': 'ink',
            'url': '/admin/core/referencedatasuggestion/?status__exact=pending',
        },
    ]
    # '-severity' is 'urgent' before 'review' — the accident of the
    # alphabet agreeing with the desk's priorities.
    preview = list(open_events.select_related(
        'message__sender', 'conversation',
    ).order_by('-severity', '-created_at')[:6])
    return render(request, 'staff/desk.html', {
        'tiles': tiles,
        'preview': preview,
        'room': 'desk',
    })


@staff_member_required
def moderation_queue(request):
    """The queue the watcher fills — open first, urgent on top."""
    show = request.GET.get('show', 'open')
    events = ModerationEvent.objects.select_related(
        'message__sender', 'conversation', 'resolved_by',
    )
    if show == 'urgent':
        events = events.filter(status='open', severity='urgent')
    elif show == 'done':
        events = events.exclude(status='open')
    elif show == 'all':
        pass
    else:
        show = 'open'
        events = events.filter(status='open')

    rows = list(events.order_by('-created_at')[:200])
    # Urgent floats over review within the open view; history stays by date.
    if show in ('open', 'urgent'):
        rows.sort(key=lambda e: (e.severity != 'urgent', -e.created_at.timestamp()))

    counts = {
        'open': ModerationEvent.objects.filter(status='open').count(),
        'urgent': ModerationEvent.objects.filter(
            status='open', severity='urgent').count(),
    }
    return render(request, 'staff/moderation.html', {
        'rows': rows,
        'show': show,
        'counts': counts,
        'room': 'moderation',
    })


def _score_rows(scan, config):
    """The classifier's 0–1 scores, dressed for reading.

    Sorted loudest first. A category only takes a colour when the house
    is actually watching it — the tunables on ModerationSettings decide,
    so the bars always agree with what the watcher would have done.
    """
    scores = (scan.classifier_scores or {}) if scan else {}
    watched, urgent = config.watched(), config.urgent()
    rows = []
    for category, value in sorted(scores.items(), key=lambda kv: -kv[1]):
        tone = 'quiet'
        if category in watched:
            if category in urgent and value >= config.urgent_threshold:
                tone = 'urgent'
            elif value >= config.flag_threshold:
                tone = 'flagged'
            else:
                tone = 'watched'
        rows.append({
            'category': category,
            'value': value,
            'pct': round(value * 100, 2),
            'tone': tone,
            'watched': category in watched,
            'urgent_category': category in urgent,
        })
    return rows


@staff_member_required
def scan_view(request, message_id):
    """One message, everything the watcher knew about it.

    The classifier's category scores as bars against the house
    thresholds, Claude's in-context read in its own words, the watch
    terms that tripped, and the surrounding thread — because context is
    the whole reason the escalation tier exists.
    """
    message = get_object_or_404(
        Message.objects.select_related('sender', 'conversation'),
        pk=message_id,
    )
    scan = MessageScan.objects.filter(message=message).first()
    config = _config()

    thread = list(
        message.conversation.messages.select_related('sender')
        .order_by('-created_at')[:config.escalation_context_messages]
    )[::-1] if message.conversation_id else []

    events = ModerationEvent.objects.filter(message=message).select_related(
        'resolved_by').order_by('-created_at')

    return render(request, 'staff/scan.html', {
        'message': message,
        'scan': scan,
        'score_rows': _score_rows(scan, config),
        'flag_pct': round(config.flag_threshold * 100, 1),
        'urgent_pct': round(config.urgent_threshold * 100, 1),
        'verdict': (scan.escalation_verdict or None) if scan else None,
        'matched_terms': (scan.matched_terms or []) if scan else [],
        'thread': thread,
        'events': events,
        'room': 'moderation',
    })


@require_POST
@staff_member_required
def event_action(request, pk):
    """Resolve or dismiss one queue row — a decision, recorded with a name."""
    event = get_object_or_404(ModerationEvent, pk=pk)
    action = request.POST.get('action', '')
    if action in ('resolved', 'dismissed') and event.status == 'open':
        event.status = action
        event.resolved_at = timezone.now()
        event.resolved_by = request.user
        event.save(update_fields=['status', 'resolved_at', 'resolved_by'])
        flash.success(request, f'Marked {action}.')
    next_url = (request.POST.get('next') or '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('staff:moderation')


@require_POST
@staff_member_required
def message_action(request, pk):
    """Hide a message from its thread, or put it back — the same write
    the Django-admin action makes, one click closer to the evidence."""
    message = get_object_or_404(Message, pk=pk)
    action = request.POST.get('action', '')
    if action in ('hide', 'restore'):
        message.moderation_state = 'hidden' if action == 'hide' else 'ok'
        message.save(update_fields=['moderation_state'])
        flash.success(
            request,
            'Message hidden from the thread.' if action == 'hide'
            else 'Message restored to the thread.')
    return redirect('staff:scan', message_id=message.pk)
