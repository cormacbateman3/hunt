"""W1.23 — enforcement: the strike ladder, the restrictions it sets, the
excuse handshake and the nightly sweep that issues strikes.

The app had no tests of its own. Every one of these rules decides whether a
member can bid, sell, trade or buy, so a quiet regression here punishes
somebody who did nothing wrong or lets somebody off who did. The sweep is
cron-driven and nobody watches it, which is exactly why it has to be pinned.

Known ladder bugs scheduled for W5.1 (D13) are pinned with
``@expectedFailure`` and the comment "W5.1", never encoded as correct:
the 3-strike ban lifting once the strikes expire, hand-set restrictions
being overwritten by the nightly refresh, and the ``account_restricted``
notice that is declared but never sent. ``cancellation_abuse`` double
counting is left untested until W5.1 says what it should do.
"""

from datetime import timedelta
from decimal import Decimal
from unittest import expectedFailure

from django.contrib.auth.models import AnonymousUser, User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Address
from apps.core.models import MarketplaceSettings
from apps.enforcement import handshakes
from apps.enforcement.models import AccountRestriction, OrderHandshake, Strike
from apps.enforcement.services import (
    AUCTION_PAYMENT_GRACE_HOURS,
    EXCUSE_CONFIRM_WINDOW_HOURS,
    STRIKE_WINDOW_DAYS,
    active_strikes_for_user,
    confirm_excuse_handshake,
    enforce_capability,
    enforce_deterministic_policies,
    initiate_excuse_handshake,
    is_buy_now_blocked,
    issue_strike,
    refresh_account_restriction,
    refresh_all_account_restrictions,
)
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.trades.models import Trade, TradeShipment

CAPABILITIES = ('bid', 'sell', 'trade')


def _with_address(user):
    address = Address.objects.create(
        user=user, full_name=user.username, line1='1 Main St', city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=True,
    )
    user.profile.shipping_address = address
    user.profile.save(update_fields=['shipping_address'])


class EnforcementBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('enf_seller', password='pw')
        cls.buyer = User.objects.create_user('enf_buyer', password='pw')
        cls.outsider = User.objects.create_user('enf_outsider', password='pw')
        # A seller with an address, so payment is never on hold on their side.
        _with_address(cls.seller)

    def _order(self, seller=None, **kwargs):
        seller = seller or self.seller
        listing = Listing.objects.create(
            seller=seller, listing_type='buy_now', title='1936 Potter Resident',
            description='x', condition_grade='good', buy_now_price=Decimal('40'),
            status='sold',
        )
        defaults = {
            'listing': listing, 'buyer': self.buyer, 'seller': seller,
            'order_type': 'buy_now', 'status': 'paid',
            'item_amount': Decimal('40.00'), 'total_amount': Decimal('45.00'),
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    def _strike(self, user=None, *, days_ago=0, reason='non_shipment', **kwargs):
        """A strike created ``days_ago``, running its full year from then."""
        created = timezone.now() - timedelta(days=days_ago)
        strike = Strike.objects.create(
            user=user or self.seller, reason=reason,
            expires_at=created + timedelta(days=STRIKE_WINDOW_DAYS), **kwargs)
        Strike.objects.filter(pk=strike.pk).update(created_at=created)
        strike.refresh_from_db()
        return strike

    def _restriction(self, user=None):
        return AccountRestriction.objects.get(user=user or self.seller)

    def assertAllowed(self, user, capability):
        allowed, reason = enforce_capability(user, capability)
        self.assertTrue(allowed, f'{capability} was refused: {reason}')
        self.assertEqual(reason, '')

    def assertRefused(self, user, capability):
        allowed, reason = enforce_capability(user, capability)
        self.assertFalse(allowed, f'{capability} was allowed')
        self.assertTrue(reason, f'{capability} was refused without a reason')
        return reason


# ── issue_strike ─────────────────────────────────────────────────────────

class IssueStrikeTests(EnforcementBase):
    def test_a_strike_runs_for_a_year_and_the_member_is_told(self):
        order = self._order()
        before = timezone.now()
        strike, created = issue_strike(
            user=self.seller, reason='non_shipment', related_order=order, notes='late')

        self.assertTrue(created)
        self.assertEqual(strike.user, self.seller)
        self.assertEqual(strike.related_order, order)
        self.assertFalse(strike.is_excused)
        self.assertGreaterEqual(strike.expires_at, before + timedelta(days=STRIKE_WINDOW_DAYS))
        self.assertLessEqual(strike.expires_at, timezone.now() + timedelta(days=STRIKE_WINDOW_DAYS))

        note = Notification.objects.get(user=self.seller, notification_type='strike_issued')
        self.assertEqual(note.link_url, f'/orders/{order.pk}/')
        self.assertIn('non shipment', note.message)

    def test_the_same_order_is_struck_once_for_the_same_reason(self):
        order = self._order()
        issue_strike(user=self.seller, reason='non_shipment', related_order=order)
        strike, created = issue_strike(user=self.seller, reason='non_shipment', related_order=order)

        self.assertIsNone(strike)
        self.assertFalse(created)
        self.assertEqual(Strike.objects.filter(user=self.seller).count(), 1)
        self.assertEqual(
            Notification.objects.filter(user=self.seller, notification_type='strike_issued').count(), 1)

    def test_another_order_or_another_reason_is_a_strike_of_its_own(self):
        first, second = self._order(), self._order()
        issue_strike(user=self.seller, reason='non_shipment', related_order=first)
        _, other_order = issue_strike(user=self.seller, reason='non_shipment', related_order=second)
        _, other_reason = issue_strike(user=self.seller, reason='other', related_order=first)

        self.assertTrue(other_order)
        self.assertTrue(other_reason)
        self.assertEqual(Strike.objects.filter(user=self.seller).count(), 3)

    def test_a_trade_strike_links_to_the_trade(self):
        trade = Trade.objects.create(initiator=self.seller, counterparty=self.buyer)
        strike, _ = issue_strike(user=self.seller, reason='non_shipment', related_trade=trade)
        self.assertEqual(strike.related_trade, trade)
        note = Notification.objects.get(user=self.seller, notification_type='strike_issued')
        self.assertEqual(note.link_url, f'/trades/{trade.pk}/')

    def test_issuing_a_strike_moves_the_member_up_the_ladder_at_once(self):
        issue_strike(user=self.seller, reason='non_shipment', related_order=self._order())
        self.assertRefused(self.seller, 'buy_now')
        self.assertAllowed(self.seller, 'bid')

        issue_strike(user=self.seller, reason='non_shipment', related_order=self._order())
        for capability in CAPABILITIES:
            self.assertRefused(self.seller, capability)


# ── The ladder: what 0, 1, 2 and 3 active strikes do ─────────────────────

class LadderTests(EnforcementBase):
    def test_with_no_strikes_nothing_is_restricted(self):
        restriction = refresh_account_restriction(self.seller)
        self.assertTrue(restriction.can_bid)
        self.assertTrue(restriction.can_sell)
        self.assertTrue(restriction.can_trade)
        self.assertIsNone(restriction.suspended_until)
        for capability in CAPABILITIES + ('buy_now',):
            self.assertAllowed(self.seller, capability)

    def test_one_strike_is_a_fortnight_off_buy_now_and_nothing_else(self):
        strike = self._strike(days_ago=2)
        restriction = refresh_account_restriction(self.seller)

        self.assertEqual(restriction.suspended_until, strike.created_at + timedelta(days=14))
        self.assertTrue(is_buy_now_blocked(self.seller))
        self.assertRefused(self.seller, 'buy_now')
        for capability in CAPABILITIES:
            self.assertAllowed(self.seller, capability)

    def test_after_the_fortnight_buy_now_comes_back_though_the_strike_still_counts(self):
        self._strike(days_ago=15)
        refresh_account_restriction(self.seller)

        self.assertEqual(active_strikes_for_user(self.seller).count(), 1)
        self.assertFalse(is_buy_now_blocked(self.seller))
        self.assertAllowed(self.seller, 'buy_now')

    def test_two_strikes_suspend_bidding_selling_and_trading_for_thirty_days(self):
        self._strike(days_ago=40)
        latest = self._strike(days_ago=3)
        restriction = refresh_account_restriction(self.seller)

        self.assertFalse(restriction.can_bid)
        self.assertFalse(restriction.can_sell)
        self.assertFalse(restriction.can_trade)
        # Thirty days from the most recent strike, not the first.
        self.assertEqual(restriction.suspended_until, latest.created_at + timedelta(days=30))
        self.assertRefused(self.seller, 'buy_now')

    def test_the_suspension_ends_thirty_days_after_the_latest_strike(self):
        self._strike(days_ago=60)
        self._strike(days_ago=31)
        restriction = refresh_account_restriction(self.seller)

        self.assertLess(restriction.suspended_until, timezone.now())
        for capability in CAPABILITIES + ('buy_now',):
            self.assertAllowed(self.seller, capability)

    def test_three_strikes_bar_the_account(self):
        for days_ago in (100, 50, 1):
            self._strike(days_ago=days_ago)
        restriction = refresh_account_restriction(self.seller)

        self.assertFalse(restriction.can_bid)
        self.assertFalse(restriction.can_sell)
        self.assertFalse(restriction.can_trade)
        for capability in CAPABILITIES + ('buy_now',):
            self.assertRefused(self.seller, capability)

    @expectedFailure  # W5.1 (D13): the ban is a 3650-day suspension the sweep recomputes.
    def test_a_three_strike_ban_does_not_lift_when_the_strikes_expire(self):
        for days_ago in (3, 2, 1):
            self._strike(days_ago=days_ago)
        refresh_account_restriction(self.seller)

        # A year on, the strikes have run out — but a ban is permanent until
        # staff lift it.
        Strike.objects.filter(user=self.seller).update(
            expires_at=timezone.now() - timedelta(days=1))
        refresh_all_account_restrictions()

        self.assertRefused(self.seller, 'bid')

    @expectedFailure  # W5.1 (D13): the nightly refresh overwrites what staff set.
    def test_a_restriction_staff_set_by_hand_survives_the_nightly_refresh(self):
        AccountRestriction.objects.create(user=self.outsider, can_sell=False)
        refresh_all_account_restrictions()
        self.assertFalse(self._restriction(self.outsider).can_sell)

    @expectedFailure  # W5.1: `account_restricted` is declared but never sent.
    def test_a_member_is_told_when_their_account_is_restricted(self):
        issue_strike(user=self.seller, reason='non_shipment', related_order=self._order())
        issue_strike(user=self.seller, reason='non_shipment', related_order=self._order())
        self.assertTrue(Notification.objects.filter(
            user=self.seller, notification_type='account_restricted').exists())


# ── Strikes run out, and excused ones never count ────────────────────────

class StrikeExpiryTests(EnforcementBase):
    def test_a_strike_past_its_year_stops_counting(self):
        self._strike(days_ago=STRIKE_WINDOW_DAYS + 1)
        self.assertFalse(active_strikes_for_user(self.seller).exists())

        restriction = refresh_account_restriction(self.seller)
        self.assertIsNone(restriction.suspended_until)
        self.assertAllowed(self.seller, 'buy_now')

    def test_strikes_are_counted_as_of_the_moment_asked(self):
        strike = self._strike(days_ago=STRIKE_WINDOW_DAYS - 10)
        self.assertIn(strike, active_strikes_for_user(self.seller))
        later = timezone.now() + timedelta(days=11)
        self.assertNotIn(strike, active_strikes_for_user(self.seller, at_time=later))

    def test_an_excused_strike_does_not_count(self):
        self._strike(days_ago=1, is_excused=True)
        self.assertFalse(active_strikes_for_user(self.seller).exists())

    def test_the_nightly_refresh_lifts_what_has_lapsed(self):
        old = self._strike(days_ago=300)
        self._strike(days_ago=5)
        refresh_account_restriction(self.seller)
        self.assertFalse(self._restriction().can_bid)   # two strikes: suspended

        # Time passes and the old strike runs out: one strike is a warning.
        Strike.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        refresh_all_account_restrictions()

        for capability in CAPABILITIES:
            self.assertAllowed(self.seller, capability)
        self.assertRefused(self.seller, 'buy_now')      # still inside the fortnight

    def test_the_nightly_refresh_reaches_everyone_with_a_strike_or_a_record(self):
        self._strike(days_ago=1)
        AccountRestriction.objects.create(user=self.outsider)

        self.assertEqual(refresh_all_account_restrictions(), 2)
        self.assertFalse(AccountRestriction.objects.filter(user=self.buyer).exists())


# ── enforce_capability ───────────────────────────────────────────────────

class EnforceCapabilityTests(EnforcementBase):
    def test_a_signed_out_visitor_is_asked_to_sign_in(self):
        visitor = AnonymousUser()
        for capability in CAPABILITIES + ('buy_now',):
            self.assertEqual(enforce_capability(visitor, capability),
                             (False, 'Authentication required.'))
        self.assertFalse(is_buy_now_blocked(visitor))

    def test_a_member_with_no_record_may_do_everything(self):
        self.assertFalse(AccountRestriction.objects.filter(user=self.outsider).exists())
        for capability in CAPABILITIES + ('buy_now',):
            self.assertAllowed(self.outsider, capability)

    def test_each_refusal_says_what_is_restricted(self):
        AccountRestriction.objects.create(
            user=self.outsider, can_bid=False, can_sell=False, can_trade=False,
            suspended_until=timezone.now() + timedelta(days=1))

        self.assertIn('Bidding', self.assertRefused(self.outsider, 'bid'))
        self.assertIn('Selling', self.assertRefused(self.outsider, 'sell'))
        self.assertIn('Trading', self.assertRefused(self.outsider, 'trade'))
        self.assertIn('Buy-now', self.assertRefused(self.outsider, 'buy_now'))

    def test_one_capability_off_leaves_the_others_alone(self):
        AccountRestriction.objects.create(user=self.outsider, can_trade=False)
        self.assertRefused(self.outsider, 'trade')
        self.assertAllowed(self.outsider, 'bid')
        self.assertAllowed(self.outsider, 'sell')
        self.assertAllowed(self.outsider, 'buy_now')

    def test_a_suspension_that_has_ended_no_longer_blocks_buy_now(self):
        AccountRestriction.objects.create(
            user=self.outsider, suspended_until=timezone.now() - timedelta(minutes=1))
        self.assertAllowed(self.outsider, 'buy_now')


# ── The excuse handshake on an issued strike ─────────────────────────────

class StrikeExcuseHandshakeTests(EnforcementBase):
    def setUp(self):
        self.order = self._order()
        self.strike, _ = issue_strike(
            user=self.seller, reason='non_shipment', related_order=self.order)

    def _initiate(self, actor=None, reason='agreed_delay', note='Buyer said no rush'):
        return initiate_excuse_handshake(
            strike=self.strike, actor=actor or self.seller,
            excuse_reason=reason, excuse_note=note)

    def test_a_participant_starts_it_and_the_other_side_is_asked(self):
        before = timezone.now()
        ok, error = self._initiate()
        self.assertTrue(ok, error)

        self.strike.refresh_from_db()
        self.assertEqual(self.strike.excuse_initiated_by, self.seller)
        self.assertEqual(self.strike.excuse_reason, 'agreed_delay')
        self.assertEqual(self.strike.excuse_note, 'Buyer said no rush')
        self.assertFalse(self.strike.is_excused)
        self.assertGreaterEqual(
            self.strike.excuse_expires_at, before + timedelta(hours=EXCUSE_CONFIRM_WINDOW_HOURS))

        asked = Notification.objects.get(user=self.buyer, notification_type='handshake_requested')
        self.assertEqual(asked.link_url, f'/orders/{self.order.pk}/')

    def test_starting_it_alone_excuses_nothing(self):
        self._initiate()
        self.assertEqual(active_strikes_for_user(self.seller).count(), 1)
        self.assertRefused(self.seller, 'buy_now')

    def test_the_note_is_trimmed_to_what_the_field_holds(self):
        self._initiate(note='  ' + 'n' * 400 + '  ')
        self.strike.refresh_from_db()
        self.assertEqual(len(self.strike.excuse_note), 250)

    def test_a_stranger_cannot_start_one(self):
        ok, error = self._initiate(actor=self.outsider)
        self.assertFalse(ok)
        self.assertIn('participants', error)
        self.strike.refresh_from_db()
        self.assertIsNone(self.strike.excuse_initiated_by)

    def test_the_other_side_confirms_and_the_strike_is_excused(self):
        self._initiate()
        ok, error = confirm_excuse_handshake(strike=self.strike, actor=self.buyer)
        self.assertTrue(ok, error)

        self.strike.refresh_from_db()
        self.assertTrue(self.strike.is_excused)
        self.assertEqual(self.strike.excuse_confirmed_by, self.buyer)
        self.assertIsNotNone(self.strike.excuse_confirmed_at)
        self.assertFalse(active_strikes_for_user(self.seller).exists())
        # The ladder is recomputed on the spot, not at the next nightly run.
        self.assertAllowed(self.seller, 'buy_now')
        self.assertTrue(Notification.objects.filter(
            user=self.seller, notification_type='strike_excused').exists())

    def test_either_side_may_start_it(self):
        ok, _ = self._initiate(actor=self.buyer)
        self.assertTrue(ok)
        ok, error = confirm_excuse_handshake(strike=self.strike, actor=self.seller)
        self.assertTrue(ok, error)

    def test_the_one_who_started_it_cannot_confirm_it(self):
        self._initiate()
        ok, error = confirm_excuse_handshake(strike=self.strike, actor=self.seller)
        self.assertFalse(ok)
        self.assertIn('self-confirm', error)
        self.strike.refresh_from_db()
        self.assertFalse(self.strike.is_excused)

    def test_nothing_to_confirm_until_somebody_starts_it(self):
        ok, error = confirm_excuse_handshake(strike=self.strike, actor=self.buyer)
        self.assertFalse(ok)
        self.assertIn('No handshake', error)

    def test_a_stranger_cannot_confirm_one(self):
        self._initiate()
        ok, _ = confirm_excuse_handshake(strike=self.strike, actor=self.outsider)
        self.assertFalse(ok)
        self.strike.refresh_from_db()
        self.assertFalse(self.strike.is_excused)

    def test_a_lapsed_handshake_leaves_the_strike_standing(self):
        self._initiate()
        Strike.objects.filter(pk=self.strike.pk).update(
            excuse_expires_at=timezone.now() - timedelta(minutes=1))
        self.strike.refresh_from_db()

        ok, error = confirm_excuse_handshake(strike=self.strike, actor=self.buyer)
        self.assertFalse(ok)
        self.assertIn('expired', error)
        self.strike.refresh_from_db()
        self.assertFalse(self.strike.is_excused)
        self.assertEqual(active_strikes_for_user(self.seller).count(), 1)

    def test_an_excused_strike_is_finished_with(self):
        self._initiate()
        confirm_excuse_handshake(strike=self.strike, actor=self.buyer)
        self.strike.refresh_from_db()

        ok, error = self._initiate(actor=self.buyer)
        self.assertFalse(ok)
        self.assertIn('already excused', error)
        ok, _ = confirm_excuse_handshake(strike=self.strike, actor=self.seller)
        self.assertFalse(ok)

    def test_on_a_trade_the_two_traders_are_the_parties(self):
        trade = Trade.objects.create(initiator=self.buyer, counterparty=self.seller)
        strike, _ = issue_strike(user=self.seller, reason='non_shipment', related_trade=trade)

        ok, _ = initiate_excuse_handshake(
            strike=strike, actor=self.outsider, excuse_reason='local_pickup')
        self.assertFalse(ok)

        ok, _ = initiate_excuse_handshake(
            strike=strike, actor=self.seller, excuse_reason='local_pickup')
        self.assertTrue(ok)
        asked = Notification.objects.get(user=self.buyer, notification_type='handshake_requested')
        self.assertEqual(asked.link_url, f'/trades/{trade.pk}/')

        ok, error = confirm_excuse_handshake(strike=strike, actor=self.buyer)
        self.assertTrue(ok, error)
        strike.refresh_from_db()
        self.assertTrue(strike.is_excused)


# ── The handshake before the deadline (handshakes.py) ────────────────────
# apps/orders/tests_ledger.py covers proposing, confirming, lapsing and the
# sweep honouring it. These are the rules it leaves out.

class OrderHandshakeRuleTests(EnforcementBase):
    def setUp(self):
        self.order = self._order()

    def _propose(self, actor=None, covers='shipping', reason='local_pickup'):
        return handshakes.propose(
            order=self.order, actor=actor or self.seller, covers=covers, reason=reason)

    def test_an_offer_waiting_on_them_is_not_offered_twice(self):
        self._propose()
        again, error = self._propose()
        self.assertIsNone(again)
        self.assertIn('already offered', error)

        theirs, error = self._propose(actor=self.buyer)
        self.assertIsNone(theirs)
        self.assertIn('Confirm it instead', error)
        self.assertEqual(OrderHandshake.objects.filter(order=self.order).count(), 1)

    def test_a_settled_deadline_takes_no_new_offers(self):
        handshake, _ = self._propose()
        handshakes.confirm(handshake=handshake, actor=self.buyer)
        again, error = self._propose(actor=self.buyer)
        self.assertIsNone(again)
        self.assertIn('already settled', error)

    def test_a_reason_and_a_real_deadline_are_required(self):
        self.assertIsNone(self._propose(reason='because')[0])
        self.assertIsNone(self._propose(covers='payment')[0])
        self.assertFalse(OrderHandshake.objects.filter(order=self.order).exists())

    def test_only_the_one_who_offered_it_can_take_it_back(self):
        handshake, _ = self._propose()
        ok, _ = handshakes.withdraw(handshake=handshake, actor=self.buyer)
        self.assertFalse(ok)

        ok, error = handshakes.withdraw(handshake=handshake, actor=self.seller)
        self.assertTrue(ok, error)
        self.assertIsNone(handshakes.open_for(self.order, 'shipping'))

    def test_a_withdrawn_offer_cannot_be_agreed_to(self):
        handshake, _ = self._propose()
        handshakes.withdraw(handshake=handshake, actor=self.seller)
        handshake.refresh_from_db()
        ok, error = handshakes.confirm(handshake=handshake, actor=self.buyer)
        self.assertFalse(ok)
        self.assertIn('withdrawn', error)
        self.assertFalse(handshakes.order_has_handshake(self.order.pk, 'shipping'))

    def test_an_agreed_handshake_cannot_be_taken_back(self):
        handshake, _ = self._propose()
        handshakes.confirm(handshake=handshake, actor=self.buyer)
        handshake.refresh_from_db()
        ok, _ = handshakes.withdraw(handshake=handshake, actor=self.seller)
        self.assertFalse(ok)
        self.assertTrue(handshakes.order_has_handshake(self.order.pk, 'shipping'))

    def test_the_database_refuses_a_handshake_agreed_by_its_proposer(self):
        handshake, _ = self._propose()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderHandshake.objects.filter(pk=handshake.pk).update(
                confirmed_by=self.seller, confirmed_at=timezone.now())

    def test_the_database_refuses_a_half_written_agreement(self):
        handshake, _ = self._propose()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderHandshake.objects.filter(pk=handshake.pk).update(confirmed_by=self.buyer)

    def test_a_shipping_handshake_does_not_excuse_a_missed_payment(self):
        """Whoever agreed to wait for the parcel did not agree to that."""
        order = self._order(order_type='auction', status='pending_payment')
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=AUCTION_PAYMENT_GRACE_HOURS + 2))
        handshake, _ = handshakes.propose(
            order=order, actor=self.buyer, covers='shipping', reason='agreed_delay')
        handshakes.confirm(handshake=handshake, actor=self.seller)

        enforce_deterministic_policies()
        self.assertTrue(Strike.objects.filter(
            user=self.buyer, related_order=order, reason='non_payment').exists())


# ── The nightly sweep ────────────────────────────────────────────────────

class NonPaymentSweepTests(EnforcementBase):
    def _unpaid_auction(self, hours_old, **kwargs):
        order = self._order(order_type='auction', status='pending_payment', **kwargs)
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_old))
        return order

    def test_an_auction_winner_who_never_pays_is_struck(self):
        order = self._unpaid_auction(AUCTION_PAYMENT_GRACE_HOURS + 1)
        self.assertEqual(enforce_deterministic_policies(), 1)

        strike = Strike.objects.get(related_order=order)
        self.assertEqual(strike.user, self.buyer)
        self.assertEqual(strike.reason, 'non_payment')
        self.assertFalse(Strike.objects.filter(user=self.seller).exists())

    def test_inside_the_grace_nobody_is_struck(self):
        self._unpaid_auction(AUCTION_PAYMENT_GRACE_HOURS - 1)
        self.assertEqual(enforce_deterministic_policies(), 0)
        self.assertFalse(Strike.objects.exists())

    def test_a_seller_without_an_address_holds_payment_so_the_buyer_is_not_struck(self):
        self._unpaid_auction(AUCTION_PAYMENT_GRACE_HOURS + 48, seller=self.outsider)
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.filter(user=self.buyer).exists())

    def test_an_unpaid_buy_now_checkout_is_not_a_broken_promise(self):
        order = self._order(order_type='buy_now', status='pending_payment')
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=3))
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.exists())

    def test_running_the_sweep_again_strikes_nobody_twice(self):
        self._unpaid_auction(AUCTION_PAYMENT_GRACE_HOURS + 1)
        enforce_deterministic_policies()
        self.assertEqual(enforce_deterministic_policies(), 0)
        self.assertEqual(Strike.objects.filter(user=self.buyer).count(), 1)


class NonShipmentSweepTests(EnforcementBase):
    """``paid_at`` is set a fortnight back so a weekend can't decide the
    outcome: the window is business days (apps/orders/clock.py)."""

    def _paid(self, days_ago=14, status='paid', **kwargs):
        return self._order(
            status=status, paid_at=timezone.now() - timedelta(days=days_ago), **kwargs)

    def test_a_seller_who_never_ships_is_struck_and_the_buyer_is_not(self):
        order = self._paid()
        self.assertEqual(enforce_deterministic_policies(), 1)
        strike = Strike.objects.get(related_order=order)
        self.assertEqual(strike.user, self.seller)
        self.assertEqual(strike.reason, 'non_shipment')
        self.assertFalse(Strike.objects.filter(user=self.buyer).exists())

    def test_a_fresh_payment_is_inside_the_window(self):
        self._paid(days_ago=1)
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.exists())

    def test_the_window_is_the_one_in_marketplace_settings(self):
        MarketplaceSettings.objects.create(ship_by_days=15)
        self._paid(days_ago=14)
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.exists())

    def test_an_order_already_on_its_way_is_never_struck(self):
        for status in ('label_created', 'in_transit', 'delivered', 'completed'):
            self._paid(status=status)
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.exists())

    def test_a_local_pickup_is_not_held_to_the_posting_deadline(self):
        self._paid(delivery_method='local_pickup')
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.exists())

    def test_an_excused_strike_is_not_issued_again_by_the_next_sweep(self):
        order = self._paid()
        enforce_deterministic_policies()
        strike = Strike.objects.get(related_order=order)
        initiate_excuse_handshake(strike=strike, actor=self.seller, excuse_reason='agreed_delay')
        confirm_excuse_handshake(strike=strike, actor=self.buyer)

        enforce_deterministic_policies()   # the next night
        self.assertFalse(Strike.objects.filter(
            related_order=order, reason='non_shipment', is_excused=False).exists())


class TradeNonShipmentSweepTests(EnforcementBase):
    def _trade(self, deadline):
        trade = Trade.objects.create(
            initiator=self.seller, counterparty=self.buyer,
            status='awaiting_shipments', ship_by_deadline=deadline)
        TradeShipment.objects.create(trade=trade, sender=self.seller, recipient=self.buyer)
        TradeShipment.objects.create(
            trade=trade, sender=self.buyer, recipient=self.seller,
            carrier='USPS', tracking_number='9400111', status='label_created')
        return trade

    def test_the_trader_who_never_posts_is_struck_and_the_one_who_did_is_not(self):
        trade = self._trade(timezone.now() - timedelta(days=1))
        self.assertEqual(enforce_deterministic_policies(), 1)

        strike = Strike.objects.get(related_trade=trade)
        self.assertEqual(strike.user, self.seller)
        self.assertEqual(strike.reason, 'non_shipment')
        self.assertFalse(Strike.objects.filter(user=self.buyer).exists())

    def test_before_the_deadline_nobody_is_struck(self):
        self._trade(timezone.now() + timedelta(days=1))
        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.exists())
