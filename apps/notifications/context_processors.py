from django.core.cache import cache

from .models import Notification

# Red means "your clock is running" (implementation plan §2): a win to
# pay for, a sale to post, staff paged. Everything else — mail, watched
# activity, outcomes — wears the neutral badge.
ACTION_TYPES = ('order_paid', 'auction_won', 'moderation_urgent')


def notifications_nav(request):
    if not request.user.is_authenticated:
        return {'nav_unread_notifications_count': 0,
                'nav_action_count': 0,
                'nav_bench_dot': False}

    unread = Notification.objects.filter(user=request.user, is_read=False)
    unread_count = unread.count()
    action_count = unread.filter(notification_type__in=ACTION_TYPES).count()

    # The Dashboard dot: something is waiting on you (an order to ship,
    # an offer expiring) — distinct from Alerts, which covers things
    # that happened. Cached briefly; it rides every page.
    key = f'bench_dot_{request.user.pk}'
    dot = cache.get(key)
    if dot is None:
        from apps.accounts.bench import needs_you_count

        dot = needs_you_count(request.user) > 0
        cache.set(key, dot, 120)

    return {'nav_unread_notifications_count': unread_count,
            'nav_action_count': action_count,
            'nav_bench_dot': bool(dot)}
