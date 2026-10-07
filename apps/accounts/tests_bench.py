"""UX revamp: My Bench → Needs you.

Every row is a deadline the platform already tracks and already acts on from
cron. These tests pin the mapping so a row can never claim a different
deadline from the job that enforces it.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.bench import (
    AUCTION_PAY_GRACE_HOURS,
    needs_you,
    needs_you_count,
)
from apps.core.models import GeographicUnit, State
from apps.collections.models import CollectionItem
from apps.listings.models import Listing
from apps.offers.models import Offer
from apps.orders.models import Order
from apps.trades.models import Trade, TradeOffer


class NeedsYouTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('bench_me', password='pw')
        cls.them = User.objects.create_user('bench_them', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania'},
        )

    def _listing(self, seller, **kwargs):
        defaults = {
            'seller': seller, 'description': 'd', 'state': self.pa,
            'condition_grade': 'good', 'status': 'active',
            'listing_type': 'buy_now', 'buy_now_price': Decimal('50'),
            'title': 'An item',
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def test_nothing_owed_means_an_empty_list(self):
        self.assertEqual(needs_you(self.me), [])
        self.assertEqual(needs_you_count(self.me), 0)

    def test_an_unpaid_order_asks_the_buyer_to_pay(self):
        order = Order.objects.create(
            listing=self._listing(self.them), buyer=self.me, seller=self.them,
            order_type='auction', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='pending_payment',
        )
        rows = needs_you(self.me)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kind'], 'pay')
        self.assertIn('Pay', rows[0]['action'])
        self.assertEqual(rows[0]['url'], reverse('orders:detail', args=[order.pk]))

    def test_the_pay_deadline_matches_the_grace_the_cron_job_enforces(self):
        order = Order.objects.create(
            listing=self._listing(self.them), buyer=self.me, seller=self.them,
            order_type='auction', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='pending_payment',
        )
        row = needs_you(self.me)[0]
        expected = order.created_at + timedelta(hours=AUCTION_PAY_GRACE_HOURS)
        self.assertEqual(row['due_at'], expected)

    def test_a_paid_order_asks_the_seller_to_ship(self):
        Order.objects.create(
            listing=self._listing(self.me), buyer=self.them, seller=self.me,
            order_type='buy_now', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='paid', delivery_method='shipping',
        )
        rows = needs_you(self.me)
        self.assertEqual([r['kind'] for r in rows], ['ship'])
        self.assertEqual(rows[0]['action'], 'Buy label')

    def test_a_local_pickup_order_never_asks_the_seller_to_ship(self):
        Order.objects.create(
            listing=self._listing(self.me), buyer=self.them, seller=self.me,
            order_type='buy_now', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='paid',
            delivery_method='local_pickup',
        )
        self.assertEqual(needs_you(self.me), [])

    def test_an_offer_on_your_listing_waits_on_you_not_on_the_offerer(self):
        listing = self._listing(self.me)
        Offer.objects.create(
            listing=listing, from_user=self.them, to_user=self.me,
            amount=Decimal('40'), status='pending',
        )
        self.assertEqual([r['kind'] for r in needs_you(self.me)], ['offer'])
        self.assertEqual(needs_you(self.them), [])

    def test_rows_are_ordered_soonest_deadline_first(self):
        far = Order.objects.create(
            listing=self._listing(self.me, title='to ship'), buyer=self.them,
            seller=self.me, order_type='buy_now', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='paid', delivery_method='shipping',
        )
        near = Order.objects.create(
            listing=self._listing(self.them, title='to pay'), buyer=self.me,
            seller=self.them, order_type='auction', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='pending_payment',
        )
        rows = needs_you(self.me)
        self.assertEqual([r['kind'] for r in rows], ['pay', 'ship'])
        self.assertLess(rows[0]['due_at'], rows[1]['due_at'])
        self.assertEqual(rows[0]['urgency'], 'now')
        del far, near

    def test_the_count_agrees_with_the_rows_it_summarises(self):
        Order.objects.create(
            listing=self._listing(self.them), buyer=self.me, seller=self.them,
            order_type='auction', item_amount=Decimal('50'),
            total_amount=Decimal('55'), status='pending_payment',
        )
        Offer.objects.create(
            listing=self._listing(self.me), from_user=self.them, to_user=self.me,
            amount=Decimal('40'), status='pending',
        )
        self.assertEqual(needs_you_count(self.me), len(needs_you(self.me)))


class UnlistedTradeTests(TestCase):
    """Since 10.10 a trade offer is usually about a piece with no lot behind
    it. The Bench read ``offer.trade_listing.title`` and ``trade.listing.title``
    unguarded, so being sent such an offer took the whole Bench down."""

    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('unlisted_me', password='pw')
        cls.them = User.objects.create_user('unlisted_them', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania'},
        )
        cls.piece = CollectionItem.objects.create(
            owner=cls.me, title='1931 Clinton resident', state=cls.pa,
            license_year=1931, condition_grade='good',
        )

    def _offer(self, **kwargs):
        defaults = {
            'subject_item': self.piece, 'trade_listing': None,
            'from_user': self.them, 'to_user': self.me, 'status': 'pending',
            'expires_at': timezone.now() + timedelta(days=3),
        }
        defaults.update(kwargs)
        return TradeOffer.objects.create(**defaults)

    def test_an_offer_on_an_unlisted_piece_names_the_piece(self):
        self._offer()
        rows = needs_you(self.me)
        self.assertEqual([r['kind'] for r in rows], ['trade_offer'])
        self.assertIn('1931 Clinton resident', rows[0]['title'])

    def test_a_live_trade_without_a_lot_names_the_piece(self):
        offer = self._offer(status='accepted')
        Trade.objects.create(
            offer=offer, listing=None, initiator=self.them, counterparty=self.me,
            status='awaiting_shipments',
            ship_by_deadline=timezone.now() + timedelta(days=5),
        )
        rows = needs_you(self.me)
        self.assertEqual([r['kind'] for r in rows], ['trade_ship'])
        self.assertIn('1931 Clinton resident', rows[0]['title'])

    def test_the_bench_page_renders_with_both(self):
        self._offer()
        Trade.objects.create(
            offer=self._offer(status='accepted'), listing=None,
            initiator=self.them, counterparty=self.me, status='accepted',
        )
        self.client.force_login(self.me)
        self.assertEqual(self.client.get(reverse('bench')).status_code, 200)


class BenchPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('page_me', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'issuance_unit_label': 'County', 'licensing_start_year': 1913},
        )

    def test_bench_requires_sign_in(self):
        resp = self.client.get(reverse('bench'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), resp.headers['Location'])

    def test_bench_renders_with_an_empty_collection(self):
        self.client.force_login(self.me)
        resp = self.client.get(reverse('bench'))
        self.assertEqual(resp.status_code, 200)
        # 16a: the green rule — this state reads as earned, never broken.
        self.assertContains(resp, 'All clear')

    def test_progress_uses_the_states_own_unit_label(self):
        """Pennsylvania issues by county; a GMU state must not say county."""
        wmd = State.objects.create(
            code='MI', name='Michigan', slug='michigan',
            issuance_unit_label='Deer Management Unit', licensing_start_year=1895,
        )
        unit = GeographicUnit.objects.create(state=wmd, name='DMU 117', slug='mi-117')
        GeographicUnit.objects.create(state=wmd, name='DMU 118', slug='mi-118')
        CollectionItem.objects.create(
            owner=self.me, title='a', state=wmd, county=unit,
            license_year=1950, condition_grade='good',
        )

        self.client.force_login(self.me)
        progress = self.client.get(reverse('bench')).context['progress']
        self.assertEqual(progress['unit_label'], 'Deer Management Units')
        self.assertEqual(progress['unit_held'], 1)
        self.assertEqual(progress['unit_total'], 2)
        self.assertEqual(progress['unit_pct'], 50)

    def test_gaps_list_units_the_collector_does_not_hold(self):
        unit_a = GeographicUnit.objects.create(state=self.pa, name='Cameron', slug='pa-cameron')
        GeographicUnit.objects.create(state=self.pa, name='Fulton', slug='pa-fulton')
        CollectionItem.objects.create(
            owner=self.me, title='a', state=self.pa, county=unit_a,
            license_year=1934, condition_grade='good',
        )

        self.client.force_login(self.me)
        progress = self.client.get(reverse('bench')).context['progress']
        self.assertIn('Fulton', progress['gaps'])
        self.assertNotIn('Cameron', progress['gaps'])

    def test_closing_soon_never_shows_you_your_own_auction(self):
        mine = Listing.objects.create(
            seller=self.me, title='mine', description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='auction',
            starting_price=Decimal('10'),
            auction_end=timezone.now() + timedelta(hours=3),
        )
        self.client.force_login(self.me)
        self.assertNotIn(mine, self.client.get(reverse('bench')).context['closing_soon'])
