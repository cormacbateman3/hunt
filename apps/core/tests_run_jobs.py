"""run_jobs is the dev stand-in for cron; it must name every periodic job.

It left out both shipment-polling commands (W1.19), so on a dev machine
tracking never moved unless a webhook arrived.
"""

from django.core.management import get_commands
from django.test import SimpleTestCase

from apps.core.management.commands.run_jobs import JOBS


class RunJobsTests(SimpleTestCase):
    def test_every_job_is_a_real_command(self):
        commands = get_commands()
        for job in JOBS:
            with self.subTest(job=job):
                self.assertIn(job, commands)

    def test_tracking_polls_run_before_auto_complete(self):
        for poll in ('poll_shipments', 'poll_trade_shipments'):
            self.assertLess(JOBS.index(poll), JOBS.index('auto_complete_orders'))
