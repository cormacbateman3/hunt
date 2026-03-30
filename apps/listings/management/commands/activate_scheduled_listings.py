from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.listings.models import Listing
from apps.notifications.services import create_notification


class Command(BaseCommand):
    help = 'Activate listings whose scheduled go-live time has arrived'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        due = Listing.objects.filter(status='scheduled', scheduled_at__lte=now).select_related(
            'seller', 'source_collection_item'
        )

        activated_count = 0

        for listing in due:
            with transaction.atomic():
                locked = Listing.objects.select_for_update().get(pk=listing.pk)
                if locked.status != 'scheduled':
                    continue

                locked.status = 'active'
                locked.save(update_fields=['status', 'updated_at'])

                # 4e: Mark collection item not trade-eligible now that listing is live
                if locked.source_collection_item:
                    locked.source_collection_item.trade_eligible = False
                    locked.source_collection_item.save(update_fields=['trade_eligible', 'updated_at'])

                create_notification(
                    user=locked.seller,
                    notification_type='listing_activated',
                    message=f'Your scheduled listing "{locked.title}" is now live.',
                    link_url=f'/listings/{locked.pk}/',
                )

                activated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Activated: {locked.title} (pk={locked.pk})')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Activated {activated_count} scheduled listing(s).')
        )
