"""
Notification services for sending emails
"""
import logging
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from . import letters
from .models import Notification

logger = logging.getLogger(__name__)

CRITICAL_EMAIL_TYPES = {
    'order_created',
    'order_paid',
    'order_shipped',
    'order_delivered',
    'trade_offer_received',
    'trade_offer_accepted',
    'strike_issued',
}


def send_notification_email(notification):
    """Send the letter for a notification.

    One shell and one builder per letter (see ``letters.py``) rather than a
    subject map of shouty labels and six near-identical templates. The
    subject is the letter's own sentence, with no ``[KeystoneBid]`` prefix:
    the sender name already says who it is from, and the front of a subject
    line is the most valuable space in an inbox — it should carry the item
    and the number, not our own name a second time.
    """
    site_url = settings.SITE_URL.rstrip('/')
    letter = letters.build(notification)

    html_message = render_to_string('emails/letter.html', {
        'letter': letter,
        'notification': notification,
        'user': notification.user,
        'settings_path': letters.settings_url(),
        'site_url': site_url,
    })

    try:
        send_mail(
            subject=letter['subject'],
            message=letters.as_text(letter, site_url),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            html_message=html_message,
            fail_silently=False,
        )

        notification.sent_email = True
        notification.save(update_fields=['sent_email'])
        return True

    except Exception:
        logger.exception('Failed to send notification email for notification_id=%s', notification.pk)
        return False


def create_notification(
    *,
    user,
    notification_type,
    message,
    link_url='',
    queue_email=False,
    dedupe_window_hours=None,
):
    """Create an in-app notification and optionally queue for email."""
    if dedupe_window_hours:
        threshold = timezone.now() - timedelta(hours=dedupe_window_hours)
        existing = Notification.objects.filter(
            user=user,
            notification_type=notification_type,
            link_url=link_url,
            message=message,
            created_at__gte=threshold,
        ).exists()
        if existing:
            return None

    should_queue_email = queue_email or notification_type in CRITICAL_EMAIL_TYPES
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        message=message,
        link_url=link_url,
        # For non-critical events, mark as already handled for email queue.
        sent_email=not should_queue_email,
    )


def mark_notification_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return notification


def mark_all_read_for_user(user):
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


def send_pending_notifications(limit=None):
    """Send queued unsent notifications."""
    pending = Notification.objects.filter(sent_email=False).select_related('user').order_by('created_at')
    if limit:
        pending = pending[:limit]

    sent_count = 0
    attempted_count = 0
    for notification in pending:
        attempted_count += 1
        if send_notification_email(notification):
            sent_count += 1

    return sent_count, attempted_count
