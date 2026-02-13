from django.core.management.base import BaseCommand
from apps.notifications.services import send_pending_notifications


class Command(BaseCommand):
    help = 'Send all pending email notifications'

    def handle(self, *args, **kwargs):
        self.stdout.write('Sending pending notifications...')

        sent_count = send_pending_notifications()

        self.stdout.write(
            self.style.SUCCESS(f'Successfully sent {sent_count} notifications')
        )
