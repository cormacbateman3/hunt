from datetime import timedelta

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.upload_stash import STASH_DIR


class Command(BaseCommand):
    help = (
        'Delete orphaned form-retry uploads from MEDIA_ROOT/tmp_uploads. A stash '
        'is normally cleared when the form saves; this sweeps the ones left by '
        'users who abandoned the form.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-hours',
            type=int,
            default=24,
            help='Only delete files last modified before this many hours ago.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be deleted without deleting it.',
        )

    def handle(self, *args, **options):
        if not default_storage.exists(STASH_DIR):
            self.stdout.write('No stash directory; nothing to do.')
            return

        cutoff = timezone.now() - timedelta(hours=options['older_than_hours'])
        _dirs, files = default_storage.listdir(STASH_DIR)
        deleted = 0
        for name in files:
            path = f'{STASH_DIR}/{name}'
            try:
                modified = default_storage.get_modified_time(path)
            except (OSError, NotImplementedError):
                continue
            if timezone.is_naive(modified):
                modified = timezone.make_aware(modified)
            if modified > cutoff:
                continue
            if options['dry_run']:
                self.stdout.write(f'would delete {path}')
            else:
                default_storage.delete(path)
            deleted += 1

        verb = 'would delete' if options['dry_run'] else 'deleted'
        self.stdout.write(self.style.SUCCESS(f'Stash sweep complete. {verb}={deleted}'))
