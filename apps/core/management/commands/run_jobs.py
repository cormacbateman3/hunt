"""One pass over every periodic job — the dev stand-in for cron.

Production runs each command on its own cron schedule; on a dev machine
nothing runs them at all, which is how an ended auction once sat "active"
for seventeen hours. `python manage.py run_jobs` does one sweep;
`--loop 60` keeps sweeping every minute until Ctrl+C.
"""

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

# Ordered roughly by how time-sensitive they are.
JOBS = (
    'close_auctions',
    'activate_scheduled_listings',
    'release_unpaid_auction_wins',
    'release_stale_buy_now',
    'expire_offers',
    'expire_trade_offers',
    'auto_complete_orders',
    'auto_complete_trades',
    'enforce_policies',
    'scan_messages',
    'enqueue_operational_notifications',
    'send_notifications',
    'clear_upload_stash',
)


class Command(BaseCommand):
    help = 'Run every periodic job once (or on a loop with --loop N seconds).'

    def add_arguments(self, parser):
        parser.add_argument('--loop', type=int, default=0, metavar='SECONDS',
                            help='Repeat every N seconds until interrupted.')

    def handle(self, *args, **options):
        interval = options['loop']
        while True:
            for job in JOBS:
                try:
                    call_command(job, verbosity=0)
                except Exception as err:  # one broken job must not stop the sweep
                    self.stderr.write(self.style.ERROR(f'{job}: {err}'))
            self.stdout.write(self.style.SUCCESS(f'Swept {len(JOBS)} jobs.'))
            if not interval:
                return
            time.sleep(interval)
