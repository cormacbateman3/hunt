"""The handshake, offered before the deadline rather than after the strike.

Two people agreeing that a deadline no longer applies is the ordinary case,
not the exception: a show pickup, a buyer who said "no rush", two lots going
in one parcel. Making them wait for a strike before they can say so turns a
rule into an unfair rule.

One party proposes and the other confirms. Only a confirmed handshake
suspends anything, and only the deadline it names.
"""

from datetime import timedelta

from django.utils import timezone

from apps.notifications.services import create_notification

from .models import OrderHandshake

# How long the other party has to answer before the proposal lapses. Matches
# the confirmation window on the post-strike excuse flow, so the two never
# disagree about how long "waiting on them" lasts.
CONFIRM_WINDOW_HOURS = 72


def _participants(order):
    return {order.buyer_id, order.seller_id}


def active_for(order, covers):
    """The confirmed handshake covering this deadline, or ``None``."""
    return (
        OrderHandshake.objects
        .filter(order=order, covers=covers, confirmed_at__isnull=False,
                withdrawn_at__isnull=True)
        .order_by('-confirmed_at')
        .first()
    )


def open_for(order, covers):
    """A proposal still waiting on an answer, or ``None``."""
    return (
        OrderHandshake.objects
        .filter(order=order, covers=covers, confirmed_at__isnull=True,
                withdrawn_at__isnull=True, expires_at__gt=timezone.now())
        .order_by('-proposed_at')
        .first()
    )


def order_has_handshake(order_id, covers):
    """Cheap check for the enforcement sweep — no order instance needed."""
    return OrderHandshake.objects.filter(
        order_id=order_id, covers=covers, confirmed_at__isnull=False,
        withdrawn_at__isnull=True,
    ).exists()


def propose(*, order, actor, covers, reason, note=''):
    """Offer a handshake. Returns ``(handshake, error)``."""
    if actor.id not in _participants(order):
        return None, 'Only the buyer and the seller can offer a handshake.'
    if covers not in dict(OrderHandshake.COVERS_CHOICES):
        return None, 'That is not a deadline a handshake can cover.'
    if reason not in dict(OrderHandshake.REASON_CHOICES):
        return None, 'Choose a reason so the other person knows what they are agreeing to.'
    if active_for(order, covers):
        return None, 'That deadline is already settled between you.'

    existing = open_for(order, covers)
    if existing:
        if existing.proposed_by_id == actor.id:
            return None, 'You have already offered one — it is waiting on them.'
        return None, 'They have offered one already. Confirm it instead.'

    handshake = OrderHandshake.objects.create(
        order=order, covers=covers, reason=reason, note=(note or '').strip()[:250],
        proposed_by=actor,
        expires_at=timezone.now() + timedelta(hours=CONFIRM_WINDOW_HOURS),
    )

    other = order.seller if actor.id == order.buyer_id else order.buyer
    create_notification(
        user=other,
        notification_type='handshake_requested',
        message=(
            f'{actor.profile.get_display_name()} offered a handshake on '
            f'"{order.listing.title}" — {handshake.get_reason_display().lower()}. '
            f'Nothing changes until you confirm it.'
        ),
        link_url=f'/orders/{order.pk}/',
    )
    return handshake, ''


def confirm(*, handshake, actor):
    """Agree to a handshake somebody else offered. Returns ``(ok, error)``."""
    order = handshake.order
    if actor.id not in _participants(order):
        return False, 'Only the buyer and the seller can confirm a handshake.'
    if handshake.proposed_by_id == actor.id:
        return False, 'The other person has to confirm it — that is the point.'
    if handshake.is_confirmed:
        return False, 'Already agreed.'
    if handshake.withdrawn_at:
        return False, 'That offer was withdrawn.'
    if handshake.expires_at <= timezone.now():
        return False, 'That offer has lapsed. Ask for a new one.'

    handshake.confirmed_by = actor
    handshake.confirmed_at = timezone.now()
    handshake.save(update_fields=['confirmed_by', 'confirmed_at'])

    create_notification(
        user=handshake.proposed_by,
        notification_type='handshake_confirmed',
        message=(
            f'{actor.profile.get_display_name()} agreed to the handshake on '
            f'"{order.listing.title}". That deadline no longer applies.'
        ),
        link_url=f'/orders/{order.pk}/',
    )
    return True, ''


def withdraw(*, handshake, actor):
    """Take back an offer nobody has answered."""
    if handshake.proposed_by_id != actor.id:
        return False, 'Only the person who offered it can take it back.'
    if handshake.is_confirmed:
        return False, 'It has already been agreed — talk to them instead.'
    handshake.withdrawn_at = timezone.now()
    handshake.save(update_fields=['withdrawn_at'])
    return True, ''
