from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services, threads
from .models import Block, Conversation, Message, MessageRead, MessageReport


@login_required
def inbox(request):
    """Messages — lands on your freshest thread, list in the left pane.

    An empty right pane taught nobody anything; the inbox now opens the
    most recent conversation the way a mail desk opens the top letter.
    Only a genuinely empty inbox keeps the (compact) empty state.
    """
    rows = _conversation_rows(request.user)
    which = request.GET.get('show', '')
    if rows and not which:
        return redirect('messaging:conversation_detail', pk=rows[0]['conversation'].pk)
    return render(request, 'messaging/inbox.html', {
        'conv_rows': rows,
        'filters': _inbox_filters(rows, which),
        'which': which,
    })


def _conversation_rows(user):
    """The left pane. Shared by the inbox and by any open thread — reading a
    reply used to lose the list, because they were separate pages."""
    convs = (
        Conversation.objects.filter(
            Q(user_a=user) | Q(user_b=user) | Q(members__user=user)
        )
        .distinct()
        .select_related('user_a__profile', 'user_b__profile', 'listing')
        .annotate(freshest=Coalesce('last_message_at', 'created_at'))
        .order_by('-freshest')
    )
    read_map = {
        r.conversation_id: r.last_read_at
        for r in MessageRead.objects.filter(user=user, conversation__in=convs)
    }

    rows = []
    for conv in convs:
        last_read = read_map.get(conv.pk)
        unread_qs = (
            Message.objects.filter(conversation=conv, is_deleted=False)
            .exclude(sender=user)
        )
        if last_read:
            unread_qs = unread_qs.filter(created_at__gt=last_read)
        snippet = (
            Message.objects.filter(conversation=conv, is_deleted=False)
            .exclude(moderation_state='hidden')
            .order_by('-created_at')
            .first()
        )
        if conv.is_group:
            member_count = conv.members.count()
            rows.append({
                'conversation': conv,
                'other': None,
                'is_group': True,
                'snippet': snippet,
                'has_unread': unread_qs.exists(),
                'context': {'label': f'{member_count} of you', 'live': False},
                'open_deal': False,
            })
            continue
        # The 8d row: person first, the deal of the moment as a context line.
        context = threads.thread_context(conv, user)
        rows.append({
            'conversation': conv,
            'other': conv.other_participant(user),
            'is_group': False,
            'snippet': snippet,
            'has_unread': unread_qs.exists(),
            'context': context,
            'open_deal': context['live'],
        })
    return rows


def _inbox_filters(rows, active):
    counts = {
        '': len(rows),
        'unread': sum(1 for row in rows if row['has_unread']),
        'deals': sum(1 for row in rows if row['open_deal']),
        'rooms': sum(1 for row in rows if row['is_group']),
    }
    return [
        {'key': key, 'label': label, 'count': counts[key], 'active': active == key}
        for key, label in (('', 'All'), ('unread', 'Unread'),
                           ('deals', 'Open deals'), ('rooms', 'Rooms'))
    ]


@login_required
def conversation_detail(request, pk):
    """View a conversation thread and optionally send a new message."""
    conv = get_object_or_404(
        Conversation.objects.select_related(
            'user_a__profile', 'user_b__profile', 'listing'
        ),
        pk=pk,
    )
    if not conv.is_participant(request.user):
        raise Http404

    other = conv.other_participant(request.user)

    msgs = (
        Message.objects.filter(conversation=conv, is_deleted=False)
        .exclude(moderation_state='hidden')
        .select_related('sender')
        .order_by('created_at')
    )

    # Mark as read
    MessageRead.objects.update_or_create(
        conversation=conv,
        user=request.user,
        defaults={'last_read_at': timezone.now()},
    )

    user_has_blocked_other = bool(other) and Block.objects.filter(
        blocker=request.user, blocked=other).exists()
    is_blocked = bool(other) and (user_has_blocked_other or Block.objects.filter(
        blocker=other, blocked=request.user).exists())

    send_error = None
    if request.method == 'POST' and 'body' in request.POST:
        body = (request.POST.get('body') or '').strip()
        if not body:
            send_error = 'Message cannot be empty.'
        else:
            _, status = services.send_message(conv, request.user, body)
            if status == 'sent':
                return redirect('messaging:conversation_detail', pk=conv.pk)
            elif status == 'rate_limited':
                send_error = 'You are sending messages too quickly. Please wait before sending again.'
            elif status == 'cooldown':
                send_error = 'Please wait 30 minutes before sending another message — the other party has not replied yet.'
            elif status == 'conversation_closed':
                send_error = 'This conversation is closed.'
            else:
                send_error = 'Cannot send message at this time.'

    members = (
        conv.members.select_related('user__profile').order_by('joined_at')
        if conv.is_group else None
    )
    # "· read" under your own bubbles, from the other side's read record.
    other_last_read = None
    if other:
        record = MessageRead.objects.filter(conversation=conv, user=other).first()
        other_last_read = record.last_read_at if record else None

    rows = _conversation_rows(request.user)
    which = request.GET.get('show', '')
    return render(request, 'messaging/conversation_detail.html', {
        'conversation': conv,
        'conv_rows': rows,
        'filters': _inbox_filters(rows, which),
        'which': which,
        'deal': None if conv.is_group else threads.deal_strip(conv, request.user),
        'members': members,
        'other': other,
        # Named thread_messages: the bare name 'messages' shadowed the
        # django.contrib.messages context processor, so no toast ever
        # rendered on the thread page.
        'thread_messages': msgs,
        'other_last_read': other_last_read,
        # The quiet word shown once, on a brand-new exchange only.
        'is_new_exchange': not msgs.exists(),
        'is_blocked': is_blocked,
        'user_has_blocked_other': user_has_blocked_other,
        'send_error': send_error,
        'report_reasons': MessageReport.REASON_CHOICES,
    })


@login_required
def start_conversation_view(request):
    """POST-only: start or resume a conversation, then redirect to it."""
    if request.method != 'POST':
        return redirect('messaging:inbox')

    recipient_id = request.POST.get('recipient_id', '').strip()
    listing_id = request.POST.get('listing_id', '').strip()
    trade_offer_id = request.POST.get('trade_offer_id', '').strip()

    try:
        other_user = User.objects.get(pk=int(recipient_id))
    except (User.DoesNotExist, ValueError, TypeError):
        messages.error(request, 'User not found.')
        return redirect(request.META.get('HTTP_REFERER') or 'messaging:inbox')

    if other_user.pk == request.user.pk:
        messages.error(request, 'You cannot message yourself.')
        return redirect(request.META.get('HTTP_REFERER') or 'messaging:inbox')

    listing = None
    trade_offer = None
    if listing_id:
        from apps.listings.models import Listing
        listing = Listing.objects.filter(pk=listing_id).first()
    if trade_offer_id:
        from apps.trades.models import TradeOffer
        trade_offer = TradeOffer.objects.filter(pk=trade_offer_id).first()

    conv, status = services.start_conversation(
        requesting_user=request.user,
        other_user=other_user,
        listing=listing,
        trade_offer=trade_offer,
    )

    if status in ('created', 'existing'):
        return redirect('messaging:conversation_detail', pk=conv.pk)
    elif status == 'email_not_verified':
        messages.error(request, 'Please verify your email address before sending messages.')
    elif status == 'rate_limited':
        messages.error(request, 'You are starting too many conversations. Please wait before trying again.')
    else:
        messages.error(request, 'Cannot message this user.')

    return redirect(request.META.get('HTTP_REFERER') or 'messaging:inbox')


@login_required
def block_user_view(request, pk):
    """POST-only: block the other participant in a conversation."""
    if request.method != 'POST':
        return redirect('messaging:inbox')
    conv = get_object_or_404(Conversation, pk=pk)
    if request.user.pk not in (conv.user_a_id, conv.user_b_id):
        raise Http404

    other = conv.other_participant(request.user)
    _, status = services.apply_block(request.user, other)
    if status == 'blocked':
        messages.success(request, f'You have blocked {other.username}. The conversation has been closed.')
    else:
        messages.info(request, f'You have already blocked {other.username}.')
    return redirect('messaging:inbox')


@login_required
def block_person_view(request, user_id):
    """POST-only: block somebody without needing a conversation first.

    `block_user_view` takes a conversation, so the only way to block anybody
    was to already be mid-argument with them. Blocking is most useful
    *before* that.
    """
    if request.method != 'POST':
        return redirect('accounts:profile', username=User.objects.filter(
            pk=user_id).values_list('username', flat=True).first() or '')
    other = get_object_or_404(User, pk=user_id)
    if other.pk == request.user.pk:
        messages.error(request, 'You cannot block yourself.')
        return redirect('accounts:profile', username=other.username)

    _, status = services.apply_block(request.user, other)
    if status == 'blocked':
        messages.success(
            request,
            f'You have blocked {other.username}. They cannot message you, and '
            'any conversation between you is closed. They are not told.')
    else:
        messages.info(request, f'You have already blocked {other.username}.')
    return redirect('accounts:profile', username=other.username)


@login_required
def unblock_user_view(request, user_id):
    """POST-only: unblock a previously blocked user."""
    if request.method != 'POST':
        return redirect('messaging:inbox')
    blocked_user = get_object_or_404(User, pk=user_id)
    status = services.remove_block(request.user, blocked_user)
    if status == 'unblocked':
        messages.success(request, f'{blocked_user.username} has been unblocked.')
    # Back where they came from, which is the privacy room rather than the
    # settings front door.
    return redirect(request.POST.get('next') or 'accounts:profile_edit')


@login_required
def report_message_view(request, pk, message_id):
    """POST-only: report a specific message as inappropriate."""
    if request.method != 'POST':
        return redirect('messaging:conversation_detail', pk=pk)
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.is_participant(request.user):
        raise Http404
    msg = get_object_or_404(Message, pk=message_id, conversation=conv)

    reason = request.POST.get('reason', 'other')
    notes = (request.POST.get('notes') or '').strip()[:500]
    _, status = services.file_report(
        reporter=request.user,
        reason=reason,
        notes=notes,
        message=msg,
        conversation=conv,
    )
    if status == 'filed':
        messages.success(request, "Reported. We'll look at it. Thank you.")
    else:
        messages.error(request, 'You have filed too many reports today. Please try again tomorrow.')
    return redirect('messaging:conversation_detail', pk=pk)


@login_required
def report_conversation_view(request, pk):
    """POST-only: report an entire conversation."""
    if request.method != 'POST':
        return redirect('messaging:conversation_detail', pk=pk)
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.is_participant(request.user):
        raise Http404

    reason = request.POST.get('reason', 'other')
    notes = (request.POST.get('notes') or '').strip()[:500]
    # Pointing at specific messages is optional — the picks travel on the
    # same form (form= attribute) and flag those messages for the reviewer.
    picked_ids = request.POST.getlist('message_ids')[:20]
    picked = list(
        Message.objects.filter(conversation=conv, pk__in=picked_ids)
        .exclude(sender=request.user)
    )
    _, status = services.file_report(
        reporter=request.user,
        reason=reason,
        notes=notes,
        conversation=conv,
        flag_messages=picked,
    )
    if status == 'filed':
        messages.success(request, "Conversation reported. We'll look at it. Thank you.")
    else:
        messages.error(request, 'You have filed too many reports today. Please try again tomorrow.')
    return redirect('messaging:conversation_detail', pk=pk)


# ---------------------------------------------------------------------------
# Group rooms
# ---------------------------------------------------------------------------

@login_required
def group_new(request):
    """Open a room: a name and the first few usernames.

    Unknown names are reported, not fatal — the room opens with whoever
    was found, and anybody can be added later.
    """
    if not services.get_messaging_settings().groups_enabled:
        messages.error(request, 'Group rooms are switched off right now.')
        return redirect('messaging:inbox')

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        raw = (request.POST.get('members') or '').replace(',', ' ')
        wanted = [handle.strip().lstrip('@') for handle in raw.split() if handle.strip()]
        found = list(User.objects.filter(username__in=wanted, is_active=True))
        missing = sorted(set(wanted) - {u.username for u in found})

        conv, status = services.start_group(request.user, name, found)
        if status == 'created':
            if missing:
                messages.warning(
                    request,
                    'No account called: ' + ', '.join(missing) + '. '
                    'The room opened without them — add them any time.',
                )
            return redirect('messaging:conversation_detail', pk=conv.pk)
        errors = {
            'name_required': 'Give the room a name.',
            'too_many_members': 'That is more people than a room can hold.',
            'rate_limited': 'You are opening rooms too quickly — give it an hour.',
            'email_not_verified': 'Verify your email before starting a room.',
        }
        messages.error(request, errors.get(status, 'Cannot open a room right now.'))

    return render(request, 'messaging/group_new.html', {
        'max_members': services.get_messaging_settings().group_max_members,
    })


@login_required
def group_add_member(request, pk):
    """POST-only: any member brings a friend in, by username."""
    if request.method != 'POST':
        return redirect('messaging:conversation_detail', pk=pk)
    conv = get_object_or_404(Conversation, pk=pk, is_group=True)
    username = (request.POST.get('username') or '').strip().lstrip('@')
    user = User.objects.filter(username=username, is_active=True).first()
    if not user:
        messages.error(request, f'No account called {username}.')
        return redirect('messaging:conversation_detail', pk=pk)

    _, status = services.add_group_member(conv, request.user, user)
    said = {
        'added': f'{user.username} is in.',
        'already_member': f'{user.username} is already here.',
        'blocked': 'You and that account have a block between you.',
        'room_full': 'The room is full.',
        'not_participant': 'Only members can add people.',
        'messaging_not_available': 'That account cannot be messaged.',
    }[status]
    (messages.success if status == 'added' else messages.error)(request, said)
    return redirect('messaging:conversation_detail', pk=pk)


@login_required
def group_leave(request, pk):
    """POST-only: walk out of a room."""
    if request.method != 'POST':
        return redirect('messaging:conversation_detail', pk=pk)
    conv = get_object_or_404(Conversation, pk=pk, is_group=True)
    if services.leave_group(conv, request.user) == 'left':
        messages.success(request, f'You left “{conv.name}”.')
        return redirect('messaging:inbox')
    return redirect('messaging:conversation_detail', pk=pk)


@login_required
def group_remove_member(request, pk, user_id):
    """POST-only: the creator shows somebody the door."""
    if request.method != 'POST':
        return redirect('messaging:conversation_detail', pk=pk)
    conv = get_object_or_404(Conversation, pk=pk, is_group=True)
    target = get_object_or_404(User, pk=user_id)
    status = services.remove_group_member(conv, request.user, target)
    if status == 'removed':
        messages.success(request, f'{target.username} was removed.')
    else:
        messages.error(request, 'Only the person who opened the room can remove members.')
    return redirect('messaging:conversation_detail', pk=pk)


@login_required
def user_search(request):
    """Typeahead for the member pickers — a name you can actually verify.

    Free-typing usernames and hoping was never going to work. Returns a
    small JSON list; members only ever get added by picking a real one.
    """
    from django.http import JsonResponse

    term = (request.GET.get('q') or '').strip().lstrip('@')
    if len(term) < 2:
        return JsonResponse({'results': []})
    hits = (
        User.objects.filter(username__icontains=term, is_active=True)
        .exclude(pk=request.user.pk)
        .select_related('profile')
        .order_by('username')[:8]
    )
    return JsonResponse({'results': [
        {'username': u.username, 'display': u.profile.get_display_name()}
        for u in hits
    ]})
