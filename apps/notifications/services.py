"""
Notification services for sending emails
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Notification


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

    subject = subject_map.get(notification.notification_type, 'KeystoneBid Notification')

    # Render email template
    html_message = render_to_string('emails/notification.html', {
        'notification': notification,
        'user': notification.user,
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

        notification.sent = True
        notification.save()
        return True

    except Exception as e:
        print(f"Failed to send notification email: {e}")
        return False


def send_pending_notifications():
    """Send all pending notifications"""
    pending = Notification.objects.filter(sent=False).select_related('user')

    sent_count = 0
    for notification in pending:
        if send_notification_email(notification):
            sent_count += 1

    return sent_count
