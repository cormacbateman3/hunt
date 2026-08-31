from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.listings.models import Listing
from apps.listings.services import seller_shipping_ready
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

                # A listing may not go live without a seller shipping address —
                # otherwise the buyer gets blocked (and penalized) at payment.
                if not seller_shipping_ready(locked.seller):
                    locked.status = 'pending'
                    locked.save(update_fields=['status', 'updated_at'])
                    create_notification(
                        user=locked.seller,
                        notification_type='listing_activation_blocked',
                        message=(
                            f'"{locked.title}" could not go live: add a default shipping '
                            'address in your Account settings, then re-publish the listing.'
                        ),
                        link_url=f'/listings/{locked.pk}/',
                    )
                    self.stdout.write(self.style.WARNING(
                        f'Blocked (no seller address): {locked.title} (pk={locked.pk}) -> pending'
                    ))
                    continue

                locked.status = 'active'
                # The "Listed" date is the moment it actually went up —
                # not when it was scheduled, not when it was drafted.
                locked.published_at = now
                locked.save(update_fields=['status', 'published_at', 'updated_at'])

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
