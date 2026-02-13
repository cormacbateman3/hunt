from django.core.management.base import BaseCommand
from apps.notifications.services import send_pending_notifications


class Command(BaseCommand):
    help = 'Send all pending email notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum number of queued notifications to process.',
        )

    def handle(self, *args, **kwargs):
        limit = kwargs.get('limit')
        if limit:
            self.stdout.write(f'Sending up to {limit} pending notifications...')
        else:
            self.stdout.write('Sending pending notifications...')

        sent_count, attempted_count = send_pending_notifications(limit=limit)
        failed_count = attempted_count - sent_count

        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {attempted_count} notifications: {sent_count} sent, {failed_count} failed'
            )
        )
