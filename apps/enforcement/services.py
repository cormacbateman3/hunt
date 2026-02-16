from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from apps.notifications.models import Notification
from .models import AccountRestriction, Strike


STRIKE_WINDOW_DAYS = 365
EXCUSE_CONFIRM_WINDOW_HOURS = 72
AUCTION_PAYMENT_GRACE_HOURS = 24
ORDER_SHIP_GRACE_DAYS = 5
CANCELLATION_PATTERN_WINDOW_DAYS = 90
CANCELLATION_PATTERN_THRESHOLD = 3


def _now():
    return timezone.now()


def _strike_expiry(now):
    return now + timedelta(days=STRIKE_WINDOW_DAYS)


def active_strikes_for_user(user, *, at_time=None):
    current = at_time or _now()
    return Strike.objects.filter(user=user, is_excused=False).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=current)
    )


def refresh_account_restriction(user):
    current = _now()
    active = list(active_strikes_for_user(user, at_time=current).order_by('-created_at'))
    active_count = len(active)
    restriction, _ = AccountRestriction.objects.get_or_create(user=user)

    if active_count <= 0:
        restriction.can_bid = True
        restriction.can_sell = True
        restriction.can_trade = True
        restriction.suspended_until = None
    elif active_count == 1:
        # Alpha baseline: 1 strike is a warning period affecting buy-now use.
        restriction.can_bid = True
        restriction.can_sell = True
        restriction.can_trade = True
        restriction.suspended_until = active[0].created_at + timedelta(days=14)
    elif active_count == 2:
        suspension_until = active[0].created_at + timedelta(days=30)
        is_suspended = suspension_until > current
        restriction.can_bid = not is_suspended
        restriction.can_sell = not is_suspended
        restriction.can_trade = not is_suspended
        restriction.suspended_until = suspension_until
    else:
        suspension_until = active[0].created_at + timedelta(days=3650)
        is_suspended = suspension_until > current
        restriction.can_bid = not is_suspended
        restriction.can_sell = not is_suspended
        restriction.can_trade = not is_suspended
        restriction.suspended_until = suspension_until

    restriction.save(update_fields=['can_bid', 'can_sell', 'can_trade', 'suspended_until', 'updated_at'])
    return restriction


def refresh_all_account_restrictions():
    from django.contrib.auth.models import User

    processed = 0
    user_ids = set(Strike.objects.values_list('user_id', flat=True))
    user_ids.update(AccountRestriction.objects.values_list('user_id', flat=True))
    for user in User.objects.filter(pk__in=user_ids):
        refresh_account_restriction(user)
        processed += 1
    return processed


def _has_open_matching_strike(*, user=None, user_id=None, reason, related_order=None, related_trade=None):
    strike_user_id = user_id or getattr(user, 'id', None)
    if not strike_user_id:
        return False

    queryset = Strike.objects.filter(user_id=strike_user_id, reason=reason, is_excused=False)
    if related_order:
        queryset = queryset.filter(related_order=related_order)
    if related_trade:
        queryset = queryset.filter(related_trade=related_trade)
    return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=_now())).exists()


def issue_strike(*, user, reason, related_order=None, related_trade=None, notes=''):
    if _has_open_matching_strike(
        user=user,
        reason=reason,
        related_order=related_order,
        related_trade=related_trade,
    ):
        return None, False

    strike = Strike.objects.create(
        user=user,
        reason=reason,
        related_order=related_order,
        related_trade=related_trade,
        notes=notes,
        expires_at=_strike_expiry(_now()),
    )
    refresh_account_restriction(user)
    Notification.objects.create(
        user=user,
        notification_type='strike_issued',
        message=f'A strike was issued for {strike.get_reason_display().lower()}.',
        link_url=f'/orders/{related_order.pk}/' if related_order else (
            f'/trades/{related_trade.pk}/' if related_trade else ''
        ),
    )
    return strike, True


def _participants_for_strike(strike):
    if strike.related_order_id:
        order = strike.related_order
        return {order.buyer_id, order.seller_id}
    if strike.related_trade_id:
        trade = strike.related_trade
        return {trade.initiator_id, trade.counterparty_id}
    return set()


def _counterparty_for_strike(strike, actor):
    if strike.related_order_id:
        return strike.related_order.seller if actor.id == strike.related_order.buyer_id else strike.related_order.buyer
    if strike.related_trade_id:
        return strike.related_trade.counterparty if actor.id == strike.related_trade.initiator_id else strike.related_trade.initiator
    return None


def initiate_excuse_handshake(*, strike, actor, excuse_reason, excuse_note=''):
    if strike.is_excused:
        return False, 'Strike is already excused.'
    participants = _participants_for_strike(strike)
    if actor.id not in participants:
        return False, 'Only trade/order participants can start a handshake.'

    strike.excuse_reason = excuse_reason
    strike.excuse_note = (excuse_note or '').strip()[:250]
    strike.excuse_initiated_by = actor
    strike.excuse_confirmed_by = None
    strike.excuse_confirmed_at = None
    strike.excuse_expires_at = _now() + timedelta(hours=EXCUSE_CONFIRM_WINDOW_HOURS)
    strike.save(
        update_fields=[
            'excuse_reason',
            'excuse_note',
            'excuse_initiated_by',
            'excuse_confirmed_by',
            'excuse_confirmed_at',
            'excuse_expires_at',
        ]
    )

    other_party = _counterparty_for_strike(strike, actor)
    if other_party:
        Notification.objects.create(
            user=other_party,
            notification_type='strike_issued',
            message=(
                f'Handshake requested to excuse strike #{strike.pk}. '
                f'Please confirm within {EXCUSE_CONFIRM_WINDOW_HOURS} hours.'
            ),
            link_url=f'/orders/{strike.related_order_id}/' if strike.related_order_id else (
                f'/trades/{strike.related_trade_id}/' if strike.related_trade_id else ''
            ),
        )
    return True, ''


def confirm_excuse_handshake(*, strike, actor):
    if strike.is_excused:
        return False, 'Strike is already excused.'
    if not strike.excuse_initiated_by_id:
        return False, 'No handshake has been initiated for this strike.'
    if strike.excuse_initiated_by_id == actor.id:
        return False, 'The initiator cannot self-confirm the handshake.'
    if actor.id not in _participants_for_strike(strike):
        return False, 'Only trade/order participants can confirm a handshake.'
    if strike.excuse_expires_at and strike.excuse_expires_at < _now():
        return False, 'Handshake window expired; strike remains active.'

    strike.is_excused = True
    strike.excuse_confirmed_by = actor
    strike.excuse_confirmed_at = _now()
    strike.save(update_fields=['is_excused', 'excuse_confirmed_by', 'excuse_confirmed_at'])
    refresh_account_restriction(strike.user)
    Notification.objects.create(
        user=strike.user,
        notification_type='strike_excused',
        message=f'Strike #{strike.pk} was excused by mutual handshake.',
        link_url=f'/orders/{strike.related_order_id}/' if strike.related_order_id else (
            f'/trades/{strike.related_trade_id}/' if strike.related_trade_id else ''
        ),
    )
    return True, ''


def enforce_deterministic_policies(*, now=None):
    from apps.orders.models import Order
    from apps.trades.models import Trade

    current = now or _now()
    created = 0

    auction_due = current - timedelta(hours=AUCTION_PAYMENT_GRACE_HOURS)
    stale_auction_orders = Order.objects.filter(
        order_type='auction',
        status='pending_payment',
        created_at__lte=auction_due,
    ).select_related('buyer', 'listing')
    for order in stale_auction_orders:
        _, was_created = issue_strike(
            user=order.buyer,
            reason='non_payment',
            related_order=order,
            notes='Auction winner did not complete payment in time.',
        )
        if was_created:
            created += 1

    ship_due = current - timedelta(days=ORDER_SHIP_GRACE_DAYS)
    overdue_paid_orders = Order.objects.filter(status='paid', updated_at__lte=ship_due).select_related('seller')
    for order in overdue_paid_orders:
        _, was_created = issue_strike(
            user=order.seller,
            reason='non_shipment',
            related_order=order,
            notes='Seller did not provide shipment within policy window.',
        )
        if was_created:
            created += 1

    overdue_trades = Trade.objects.filter(
        status__in=['awaiting_shipments', 'shipped_one'],
        ship_by_deadline__isnull=False,
        ship_by_deadline__lte=current,
    ).prefetch_related('shipments')
    for trade in overdue_trades:
        for shipment in trade.shipments.all():
            if shipment.status in {'pending'} and not shipment.tracking_number:
                _, was_created = issue_strike(
                    user=shipment.sender,
                    reason='non_shipment',
                    related_trade=trade,
                    notes='Trader did not provide tracking by ship-by deadline.',
                )
                if was_created:
                    created += 1

    abuse_window = current - timedelta(days=CANCELLATION_PATTERN_WINDOW_DAYS)
    offenders = (
        Strike.objects.filter(
            created_at__gte=abuse_window,
            reason__in=['non_payment', 'non_shipment'],
            is_excused=False,
        )
        .values('user')
        .annotate(total=Count('id'))
        .filter(total__gte=CANCELLATION_PATTERN_THRESHOLD)
    )
    # Cancellation abuse uses repeated non-payment/non-shipment as the deterministic pattern.
    for row in offenders:
        from django.contrib.auth.models import User
        offender = User.objects.filter(pk=row['user']).first()
        if not offender:
            continue
        _, was_created = issue_strike(
            user=offender,
            reason='cancellation_abuse',
            notes='Repeated non-payment/non-shipment behavior detected.',
        )
        if was_created:
            created += 1

    return created


def is_buy_now_blocked(user):
    if not user.is_authenticated:
        return False
    restriction = AccountRestriction.objects.filter(user=user).first()
    if not restriction:
        return False
    return bool(restriction.suspended_until and restriction.suspended_until > _now())


def enforce_capability(user, capability):
    if not user.is_authenticated:
        return False, 'Authentication required.'

    restriction = AccountRestriction.objects.filter(user=user).first()
    if capability == 'buy_now':
        if is_buy_now_blocked(user):
            return False, 'Buy-now access is temporarily restricted due to account strikes.'
        return True, ''
    if capability == 'bid':
        if restriction and not restriction.can_bid:
            return False, 'Bidding is currently restricted on your account.'
    if capability == 'sell':
        if restriction and not restriction.can_sell:
            return False, 'Selling is currently restricted on your account.'
    if capability == 'trade':
        if restriction and not restriction.can_trade:
            return False, 'Trading is currently restricted on your account.'
    return True, ''
