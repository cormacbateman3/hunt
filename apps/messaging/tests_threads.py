"""Messages — two panes, the deal pinned, and the agreement caught.

The nudge is the part worth testing hardest, because it is the one that
touches enforcement. It must appear only for the person the clock is running
against, only while there is still time, and never once something is already
on the record.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import State
from apps.enforcement import handshakes
from apps.listings.models import Listing
from apps.messaging import threads
from apps.messaging.models import Conversation, Message
from apps.orders.models import Order


class ThreadBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('ms_seller', password='pw')
        cls.buyer = User.objects.create_user('ms_buyer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def _conversation(self, listing=None):
        a, b = sorted([self.seller, self.buyer], key=lambda u: u.pk)
        return Conversation.objects.create(
            listing=listing,
            user_a=a, user_b=b, created_by=self.buyer)

    def _sale(self, status='paid'):
        listing = Listing.objects.create(
            seller=self.seller, title='1951 Elk County Non-Resident', description='d',
            state=self.pa, condition_grade='good', status='sold',
            listing_type='buy_now', buy_now_price=Decimal('138.40'))
        order = Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller,
            order_type='buy_now', status=status, item_amount=Decimal('138.40'),
            shipping_amount=Decimal('8.40'), total_amount=Decimal('146.80'))
        return listing, order


class DealStripTests(ThreadBase):
    def test_a_general_conversation_pins_nothing(self):
        conv = self._conversation()
        self.assertIsNone(threads.deal_strip(conv, self.buyer))

    def test_the_strip_says_which_side_you_are_on(self):
        listing, _ = self._sale()
        conv = self._conversation(listing)
        self.assertEqual(threads.deal_strip(conv, self.seller)['side'], 'You sold it')
        self.assertEqual(threads.deal_strip(conv, self.buyer)['side'], 'You bought it')

    def test_the_strip_carries_the_amount_and_a_way_into_the_order(self):
        listing, order = self._sale()
        conv = self._conversation(listing)
        strip = threads.deal_strip(conv, self.seller)
        self.assertEqual(strip['amount'], Decimal('146.80'))
        self.assertEqual(strip['url'], reverse('orders:detail', args=[order.pk]))

    def test_the_deadline_only_reads_as_yours_when_it_is(self):
        listing, _ = self._sale(status='paid')
        conv = self._conversation(listing)
        self.assertTrue(threads.deal_strip(conv, self.seller)['on_you'])
        self.assertFalse(threads.deal_strip(conv, self.buyer)['on_you'])


class CatchTheAgreementTests(ThreadBase):
    def test_the_nudge_goes_to_whoever_the_clock_is_running_against(self):
        listing, _ = self._sale(status='paid')
        conv = self._conversation(listing)
        self.assertIsNotNone(threads.deal_strip(conv, self.seller)['nudge'])
        self.assertIsNone(threads.deal_strip(conv, self.buyer)['nudge'])

    def test_a_settled_order_gets_no_nudge(self):
        listing, _ = self._sale(status='completed')
        conv = self._conversation(listing)
        self.assertIsNone(threads.deal_strip(conv, self.seller)['nudge'])

    def test_once_something_is_on_the_record_the_nudge_stops(self):
        listing, order = self._sale(status='paid')
        conv = self._conversation(listing)
        self.assertIsNotNone(threads.deal_strip(conv, self.seller)['nudge'])

        handshake, _ = handshakes.propose(
            order=order, actor=self.seller, covers='shipping', reason='local_pickup')
        # A proposal alone is enough to stop asking twice...
        self.assertIsNone(threads.deal_strip(conv, self.seller)['nudge'])

        # ...and so, obviously, is an agreement.
        handshakes.confirm(handshake=handshake, actor=self.buyer)
        self.assertIsNone(threads.deal_strip(conv, self.seller)['nudge'])

    def test_an_overdue_deadline_is_past_nudging(self):
        listing, order = self._sale(status='paid')
        Order.objects.filter(pk=order.pk).update(
            updated_at=timezone.now() - timedelta(days=60))
        conv = self._conversation(listing)
        # Creating the Order caches it on the in-memory Listing, so re-read
        # the conversation or the strip measures the pre-update timestamp.
        conv = Conversation.objects.get(pk=conv.pk)
        self.assertIsNone(threads.deal_strip(conv, self.seller)['nudge'])

    def test_the_nudge_never_claims_anybody_said_anything(self):
        """A machine deciding a sentence was an agreement is worse than no
        feature at all — the copy has to stay conditional."""
        listing, _ = self._sale(status='paid')
        conv = self._conversation(listing)
        Message.objects.create(conversation=conv, sender=self.buyer,
                               body='Monday is fine by me.')

        self.client.force_login(self.seller)
        html = self.client.get(
            reverse('messaging:conversation_detail', args=[conv.pk])).content.decode()
        self.assertIn('If the two of you have agreed something different', html)
        self.assertIn('Offer a handshake', html)


class TwoPaneTests(ThreadBase):
    def test_opening_a_thread_keeps_the_list(self):
        conv = self._conversation()
        Message.objects.create(conversation=conv, sender=self.buyer, body='Hello.')

        self.client.force_login(self.seller)
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertEqual(len(resp.context['conv_rows']), 1)
        self.assertContains(resp, 'ms-list')

    def test_the_inbox_is_the_same_two_panes_with_nothing_open(self):
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('messaging:inbox'))
        self.assertContains(resp, 'ms-list')
        self.assertContains(resp, 'Nothing here yet')

    def test_open_deals_can_be_filtered_to(self):
        # One thread per pair now — a second pair needs a third person.
        listing, _ = self._sale(status='paid')
        self._conversation(listing)
        quiet_friend = User.objects.create_user('ms_quiet')
        a, b = sorted([self.seller, quiet_friend], key=lambda u: u.pk)
        Conversation.objects.create(user_a=a, user_b=b, created_by=self.seller)

        self.client.force_login(self.seller)
        # The inbox opens the freshest thread now; the chips ride along.
        resp = self.client.get(reverse('messaging:inbox'), follow=True)
        counts = {chip['key']: chip['count'] for chip in resp.context['filters']}
        self.assertEqual(counts['deals'], 1)
        self.assertEqual(counts[''], 2)

    def test_a_stranger_cannot_open_the_thread(self):
        conv = self._conversation()
        self.client.force_login(User.objects.create_user('ms_nosy'))
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertEqual(resp.status_code, 404)
