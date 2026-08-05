from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services, threads
from .models import Block, Conversation, Message, MessageRead, MessageReport


@login_required
def inbox(request):
    """Messages — the same two panes as a thread, with nothing open yet."""
    rows = _conversation_rows(request.user)
    return render(request, 'messaging/inbox.html', {
        'conv_rows': rows,
        'filters': _inbox_filters(rows, request.GET.get('show', '')),
        'which': request.GET.get('show', ''),
    })


def _conversation_rows(user):
    """The left pane. Shared by the inbox and by any open thread — reading a
    reply used to lose the list, because they were separate pages."""
    convs = (
        Conversation.objects.filter(Q(user_a=user) | Q(user_b=user))
        .select_related('user_a__profile', 'user_b__profile', 'listing')
        .order_by('-last_message_at', '-created_at')
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
        order = getattr(conv.listing, 'order', None) if conv.listing_id else None
        rows.append({
            'conversation': conv,
            'other': conv.other_participant(user),
            'snippet': snippet,
            'has_unread': unread_qs.exists(),
            'open_deal': bool(order and order.status in threads.LIVE_ORDER_STATUSES),
        })
    return rows


def _inbox_filters(rows, active):
    counts = {
        '': len(rows),
        'unread': sum(1 for row in rows if row['has_unread']),
        'deals': sum(1 for row in rows if row['open_deal']),
    }
    return [
        {'key': key, 'label': label, 'count': counts[key], 'active': active == key}
        for key, label in (('', 'All'), ('unread', 'Unread'), ('deals', 'Open deals'))
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
    if request.user.pk not in (conv.user_a_id, conv.user_b_id):
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

    user_has_blocked_other = Block.objects.filter(blocker=request.user, blocked=other).exists()
    is_blocked = user_has_blocked_other or Block.objects.filter(blocker=other, blocked=request.user).exists()

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

    return render(request, 'messaging/conversation_detail.html', {
        'conversation': conv,
        'conv_rows': _conversation_rows(request.user),
        'deal': threads.deal_strip(conv, request.user),
        'other': other,
        'messages': msgs,
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
    conversation_type = request.POST.get('conversation_type', 'general')

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
        conversation_type=conversation_type,
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
    deleted, _ = Block.objects.filter(blocker=request.user, blocked=blocked_user).delete()
    if deleted:
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
    if request.user.pk not in (conv.user_a_id, conv.user_b_id):
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
        messages.success(request, 'Report submitted. Thank you.')
    else:
        messages.error(request, 'You have filed too many reports today. Please try again tomorrow.')
    return redirect('messaging:conversation_detail', pk=pk)


@login_required
def report_conversation_view(request, pk):
    """POST-only: report an entire conversation."""
    if request.method != 'POST':
        return redirect('messaging:conversation_detail', pk=pk)
    conv = get_object_or_404(Conversation, pk=pk)
    if request.user.pk not in (conv.user_a_id, conv.user_b_id):
        raise Http404

    reason = request.POST.get('reason', 'other')
    notes = (request.POST.get('notes') or '').strip()[:500]
    _, status = services.file_report(
        reporter=request.user,
        reason=reason,
        notes=notes,
        conversation=conv,
    )
    if status == 'filed':
        messages.success(request, 'Conversation reported. Thank you.')
    else:
        messages.error(request, 'You have filed too many reports today. Please try again tomorrow.')
    return redirect('messaging:conversation_detail', pk=pk)
