"""One thread per pair — the 8d rule, held down.

If Walt and John are talking, they have ONE conversation. A listing or
trade walked in through an entry point refreshes the thread's context;
it never mints a second thread. The left pane's context line and the
pinned strip both read the pair's *live* deal, not a frozen pointer.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import State
from apps.listings.models import Listing
from apps.messaging import services, threads
from apps.messaging.models import Conversation
from apps.orders.models import Order


class PairBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name):
            user = User.objects.create_user(name, password='pw')
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.walt = verified('pair_walt')
        cls.john = verified('pair_john')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def setUp(self):
        # The rate limits live in the cache, which outlives a test.
        cache.clear()

    def _listing(self, title, seller=None):
        return Listing.objects.create(
            seller=seller or self.john, title=title, description='d',
            state=self.pa, condition_grade='good', status='active',
            listing_type='buy_now', buy_now_price=Decimal('50'))


class OneThreadTests(PairBase):
    def test_two_listings_one_thread(self):
        first = self._listing('A 1931 Cameron')
        second = self._listing('A 1940 Potter')

        conv1, status1 = services.start_conversation(self.walt, self.john, listing=first)
        conv2, status2 = services.start_conversation(self.walt, self.john, listing=second)

        self.assertEqual(status1, 'created')
        self.assertEqual(status2, 'existing')
        self.assertEqual(conv1.pk, conv2.pk)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_walking_in_about_something_new_repoints_the_context(self):
        first = self._listing('A 1931 Cameron')
        second = self._listing('A 1940 Potter')
        services.start_conversation(self.walt, self.john, listing=first)
        conv, _ = services.start_conversation(self.walt, self.john, listing=second)
        self.assertEqual(conv.listing, second)

    def test_the_profile_door_and_the_listing_door_share_the_thread(self):
        listing = self._listing('A 1931 Cameron')
        self.client.force_login(self.walt)
        self.client.post(reverse('messaging:start'),
                         {'recipient_id': self.john.pk, 'listing_id': listing.pk})
        self.client.post(reverse('messaging:start'),
                         {'recipient_id': self.john.pk})
        self.assertEqual(Conversation.objects.count(), 1)

    def test_resuming_your_thread_is_never_rate_limited(self):
        """The 5-per-hour limit gates NEW conversations. Opening the one
        thread you already have must always work."""
        services.start_conversation(self.walt, self.john, listing=None)
        for _ in range(10):
            conv, status = services.start_conversation(self.walt, self.john)
            self.assertEqual(status, 'existing')

    def test_an_unverified_account_cannot_reply_either(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        lurker_profile = self.walt.profile
        lurker_profile.email_verified = False
        lurker_profile.save(update_fields=['email_verified'])
        _, status = services.send_message(conv, self.walt, 'hello')
        self.assertEqual(status, 'email_not_verified')


class ContextLineTests(PairBase):
    def test_a_live_sale_names_your_side(self):
        listing = self._listing('1951 Elk County Non-Resident')
        Order.objects.create(
            listing=listing, buyer=self.walt, seller=self.john,
            order_type='buy_now', status='paid', item_amount=Decimal('50'),
            shipping_amount=0, total_amount=Decimal('50'))
        conv, _ = services.start_conversation(self.walt, self.john, listing=listing)

        self.assertEqual(threads.thread_context(conv, self.john)['label'],
                         'Sale · 1951 Elk County Non-Resident')
        self.assertEqual(threads.thread_context(conv, self.walt)['label'],
                         'Purchase · 1951 Elk County Non-Resident')
        self.assertTrue(threads.thread_context(conv, self.walt)['live'])

    def test_no_deal_reads_as_nothing_outstanding(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        context = threads.thread_context(conv, self.walt)
        self.assertEqual(context['label'], 'Nothing outstanding')
        self.assertFalse(context['live'])

    def test_the_strip_follows_the_live_deal_not_the_old_context(self):
        """The thread was last about listing A; the pair's live order is
        about listing B — the strip must show B."""
        old = self._listing('The old talk')
        live = self._listing('The live deal')
        order = Order.objects.create(
            listing=live, buyer=self.walt, seller=self.john,
            order_type='buy_now', status='paid', item_amount=Decimal('50'),
            shipping_amount=0, total_amount=Decimal('50'))
        conv, _ = services.start_conversation(self.walt, self.john, listing=old)

        strip = threads.deal_strip(conv, self.walt)
        self.assertEqual(strip['listing'], live)
        self.assertEqual(strip['url'], reverse('orders:detail', args=[order.pk]))


class EntryCopyTests(PairBase):
    def test_the_seller_card_says_message_not_ask(self):
        """'Ask a question' is the public Q&A tab two inches away — the
        private door has to say what it opens."""
        listing = self._listing('A 1931 Cameron')
        self.client.force_login(self.walt)
        html = self.client.get(
            reverse('listings:detail', args=[listing.pk])).content.decode()
        self.assertIn('Message', html)
        self.assertNotIn('name="conversation_type"', html)
