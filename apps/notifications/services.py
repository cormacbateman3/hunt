"""
Notification services for sending emails
"""
import logging
import re
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Notification

logger = logging.getLogger(__name__)


def _extract_first_url(text):
    match = re.search(r'https?://\S+', text or '')
    return match.group(0) if match else None


def send_notification_email(notification):
    """Send an email for a notification"""

    subject_map = {
        'outbid': 'You have been outbid',
        'auction_won': 'Congratulations! You won an auction',
        'auction_sold': 'Your item sold!',
        'auction_expired': 'Your auction expired',
        'payment_received': 'Payment received',
        'payment_confirmed': 'Payment confirmed',
    }
    template_map = {
        'outbid': 'emails/notifications/outbid.html',
        'auction_won': 'emails/notifications/auction_won.html',
        'auction_sold': 'emails/notifications/auction_sold.html',
        'auction_expired': 'emails/notifications/auction_expired.html',
        'payment_received': 'emails/notifications/payment_received.html',
        'payment_confirmed': 'emails/notifications/payment_confirmed.html',
    }

    subject = subject_map.get(notification.notification_type, 'KeystoneBid Notification')
    template_name = template_map.get(notification.notification_type, 'emails/notification.html')

    html_message = render_to_string(template_name, {
        'notification': notification,
        'user': notification.user,
        'action_url': _extract_first_url(notification.message),
        'site_url': settings.SITE_URL.rstrip('/'),
    })

    try:
        send_mail(
            subject=f'[KeystoneBid] {subject}',
            message=notification.message,
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
