from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.notifications.services import create_notification
from apps.orders.models import Order
from apps.trades.models import TradeShipment


class Command(BaseCommand):
    help = 'Enqueue in-app operational reminders for shipping deadlines and receipt confirmations.'

    def handle(self, *args, **options):
        now = timezone.now()
        created = 0

        # Order ship-by reminders: paid orders approaching 5-day shipping deadline.
        order_reminder_start = now - timedelta(days=4)
        order_reminder_end = now - timedelta(days=5)
        orders_due = (
            Order.objects.filter(
                status='paid',
                updated_at__lte=order_reminder_start,
                updated_at__gt=order_reminder_end,
            )
            .select_related('seller')
        )
        for order in orders_due:
            note = create_notification(
                user=order.seller,
                notification_type='order_ship_reminder',
                message=f'Order #{order.pk} needs shipment tracking before policy deadline.',
                link_url=f'/orders/{order.pk}/',
                dedupe_window_hours=24,
            )
            if note:
                created += 1

        # Trade ship-by reminders for pending outgoing side.
        trade_due = (
            TradeShipment.objects.filter(
                trade__ship_by_deadline__isnull=False,
                trade__ship_by_deadline__lte=now + timedelta(hours=24),
                trade__ship_by_deadline__gt=now,
                status='pending',
            )
            .select_related('trade', 'sender')
        )
        for shipment in trade_due:
            note = create_notification(
                user=shipment.sender,
                notification_type='trade_ship_reminder',
                message=(
                    f'Trade #{shipment.trade_id} shipment deadline is near. '
                    'Add tracking to avoid enforcement.'
                ),
                link_url=f'/trades/{shipment.trade_id}/',
                dedupe_window_hours=24,
            )
            if note:
                created += 1

        # Receipt confirmation reminders.
        delivered_orders = (
            Order.objects.filter(status='delivered', updated_at__lte=now - timedelta(hours=24))
            .select_related('buyer')
        )
        for order in delivered_orders:
            note = create_notification(
                user=order.buyer,
                notification_type='receipt_confirmation_pending',
                message=f'Order #{order.pk} was delivered. Confirm receipt to complete the lifecycle.',
                link_url=f'/orders/{order.pk}/',
                dedupe_window_hours=24,
            )
            if note:
                created += 1

        delivered_trade_shipments = (
            TradeShipment.objects.filter(
                status='delivered',
                recipient_confirmed_at__isnull=True,
                delivered_at__lte=now - timedelta(hours=24),
            )
            .select_related('trade', 'recipient')
        )
        for shipment in delivered_trade_shipments:
            note = create_notification(
                user=shipment.recipient,
                notification_type='receipt_confirmation_pending',
                message=(
                    f'Trade #{shipment.trade_id} shipment from {shipment.sender.username} was delivered. '
                    'Confirm receipt to progress completion.'
                ),
                link_url=f'/trades/{shipment.trade_id}/',
                dedupe_window_hours=24,
            )
            if note:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'Operational notifications enqueued: {created}'))

