from django.core.management.base import BaseCommand

from apps.moderation.services import get_settings, scan_pending


class Command(BaseCommand):
    """The cron sweep: scan every message nobody has scanned yet.

    Absence of a MessageScan row is the queue, so this needs no state of
    its own and can run as often as cron likes (run_jobs includes it).
    """

    help = 'Scan unscanned messages through the moderation tiers.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None,
                            help='Override the configured batch size.')

    def handle(self, *args, **options):
        config = get_settings()
        if not config.scanning_enabled:
            self.stdout.write('Scanning is off in Moderation settings.')
            return
        counts = scan_pending(limit=options['limit'], config=config)
        self.stdout.write(self.style.SUCCESS(
            f"Scanned {counts['scanned']} message(s), flagged {counts['flagged']}."
        ))
