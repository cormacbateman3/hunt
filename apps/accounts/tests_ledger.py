"""Bids & offers — one page, split by direction.

The split that matters is not bid-versus-offer, it is *chasing* versus *on my
things*. What gets tested hardest is the third money column: a seller looking
at an offer needs to know what they would actually keep, and a buyer needs to
know what the next bid costs.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.ledger import ledger
from apps.bids.models import Bid
from apps.core.models import State
from apps.listings.models import Listing
from apps.offers.models import Offer
from apps.orders.services import calculate_platform_fee


class LedgerBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('lg_me', password='pw')
        cls.them = User.objects.create_user('lg_them', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def _auction(self, seller=None, **kwargs):
        defaults = {
            'seller': seller or self.them, 'title': 'A lot', 'description': 'd',
            'state': self.pa, 'condition_grade': 'good', 'status': 'active',
            'listing_type': 'auction', 'starting_price': Decimal('40'),
            'auction_end': timezone.now() + timedelta(hours=4),
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def _store(self, seller=None, **kwargs):
        defaults = {
            'seller': seller or self.them, 'title': 'A licence', 'description': 'd',
            'state': self.pa, 'condition_grade': 'good', 'status': 'active',
            'listing_type': 'buy_now', 'buy_now_price': Decimal('410'),
            'allow_offers': True,
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)


class ChasingTests(LedgerBase):
    def test_being_outbid_is_rust_and_offers_the_next_bid(self):
        listing = self._auction()
        Bid.objects.create(listing=listing, bidder=self.me, amount=Decimal('390'))
        Listing.objects.filter(pk=listing.pk).update(current_bid=Decimal('402'))

        row = ledger(self.me)['chasing'][0]
        self.assertEqual(row['headline'], 'You’ve been outbid')
        self.assertEqual(row['tone'], 'rust')
        self.assertEqual(row['mine'], Decimal('390'))
        self.assertEqual(row['theirs'], Decimal('402'))
        self.assertIn('next bid', row['note'])
        self.assertEqual(row['action']['label'], 'Bid again')

    def test_winning_is_green_and_asks_for_nothing(self):
        listing = self._auction()
        Bid.objects.create(listing=listing, bidder=self.me,
                           amount=Decimal('78'), is_winning=True)
        Listing.objects.filter(pk=listing.pk).update(current_bid=Decimal('78'))

        row = ledger(self.me)['chasing'][0]
        self.assertEqual(row['headline'], 'You’re winning it')
        self.assertEqual(row['tone'], 'live')
        self.assertEqual(row['action']['style'], 'text')

    def test_one_row_per_auction_at_your_highest_bid(self):
        listing = self._auction()
        for amount in ('50', '60', '70'):
            Bid.objects.create(listing=listing, bidder=self.me, amount=Decimal(amount))

        chasing = ledger(self.me)['chasing']
        self.assertEqual(len(chasing), 1)
        self.assertEqual(chasing[0]['mine'], Decimal('70'))

    def test_a_closed_auction_leaves_the_chasing_list(self):
        listing = self._auction(status='sold')
        Bid.objects.create(listing=listing, bidder=self.me, amount=Decimal('70'))
        self.assertEqual(ledger(self.me)['chasing'], [])

    def test_an_offer_you_made_can_be_withdrawn_by_post_only(self):
        listing = self._store()
        Offer.objects.create(listing=listing, from_user=self.me, to_user=self.them,
                             amount=Decimal('360'), status='pending')

        row = ledger(self.me)['chasing'][0]
        self.assertEqual(row['headline'], 'Waiting on them')
        self.assertEqual(row['action']['label'], 'Withdraw')
        self.assertTrue(row['action']['post'])

    def test_a_counter_puts_the_ball_back_in_your_court(self):
        listing = self._store()
        mine = Offer.objects.create(
            listing=listing, from_user=self.me, to_user=self.them,
            amount=Decimal('180'), status='countered')
        Offer.objects.create(
            listing=listing, from_user=self.them, to_user=self.me,
            amount=Decimal('205'), status='pending', counter_to=mine)

        chasing = ledger(self.me)['chasing']
        theirs = next(row for row in chasing if row['headline'] == 'Your turn')
        self.assertEqual(theirs['theirs'], Decimal('205'))
        self.assertIn('$205', theirs['note'])
        self.assertEqual(theirs['action']['label'], 'Decide')

    def test_what_needs_deciding_sorts_first(self):
        outbid = self._auction()
        Bid.objects.create(listing=outbid, bidder=self.me, amount=Decimal('50'))
        Listing.objects.filter(pk=outbid.pk).update(current_bid=Decimal('60'))

        quiet = self._store()
        Offer.objects.create(listing=quiet, from_user=self.me, to_user=self.them,
                             amount=Decimal('100'), status='pending',
                             expires_at=timezone.now() + timedelta(days=2))

        headlines = [row['headline'] for row in ledger(self.me)['chasing']]
        self.assertEqual(headlines[0], 'You’ve been outbid')


class OnMyThingsTests(LedgerBase):
    def test_an_offer_says_what_you_would_keep(self):
        listing = self._store(seller=self.me, buy_now_price=Decimal('285'))
        Offer.objects.create(listing=listing, from_user=self.them, to_user=self.me,
                             amount=Decimal('250'), status='pending')

        row = ledger(self.me)['on_my_things'][0]
        keep = Decimal('250') - calculate_platform_fee(Decimal('250'))
        self.assertIn(f'${keep:,.2f}', row['note'])
        self.assertEqual(row['mine'], Decimal('250'))
        self.assertEqual(row['theirs'], Decimal('285'))

    def test_the_deadline_is_in_the_headline_not_buried(self):
        listing = self._store(seller=self.me)
        Offer.objects.create(
            listing=listing, from_user=self.them, to_user=self.me,
            amount=Decimal('250'), status='pending',
            expires_at=timezone.now() + timedelta(days=2, hours=1))

        row = ledger(self.me)['on_my_things'][0]
        self.assertTrue(row['headline'].startswith('Your turn ·'))
        self.assertIn('2 days left', row['headline'])

    def test_settled_offers_are_off_the_page(self):
        listing = self._store(seller=self.me)
        offer = Offer.objects.create(
            listing=listing, from_user=self.them, to_user=self.me,
            amount=Decimal('250'), status='pending')
        self.assertEqual(len(ledger(self.me)['on_my_things']), 1)

        offer.status = 'declined'
        offer.save()
        self.assertEqual(ledger(self.me)['on_my_things'], [])

    def test_your_own_offers_never_land_in_the_other_direction(self):
        listing = self._store()
        Offer.objects.create(listing=listing, from_user=self.me, to_user=self.them,
                             amount=Decimal('100'), status='pending')
        page = ledger(self.me)
        self.assertEqual(len(page['chasing']), 1)
        self.assertEqual(page['on_my_things'], [])


class LedgerPageTests(LedgerBase):
    def test_the_page_shows_both_directions(self):
        chased = self._auction()
        Bid.objects.create(listing=chased, bidder=self.me, amount=Decimal('50'))
        mine = self._store(seller=self.me, title='Mine to sell')
        Offer.objects.create(listing=mine, from_user=self.them, to_user=self.me,
                             amount=Decimal('250'), status='pending')

        self.client.force_login(self.me)
        resp = self.client.get(reverse('bids:my_bids'))
        self.assertContains(resp, 'Chasing')
        self.assertContains(resp, 'On my things')
        self.assertContains(resp, 'Mine to sell')

    def test_an_empty_page_says_so_in_both_halves(self):
        self.client.force_login(self.me)
        resp = self.client.get(reverse('bids:my_bids'))
        self.assertContains(resp, 'Nothing out there')
        self.assertContains(resp, 'Nobody has made you an offer')

    def test_withdraw_is_a_form_not_a_link(self):
        listing = self._store()
        Offer.objects.create(listing=listing, from_user=self.me, to_user=self.them,
                             amount=Decimal('360'), status='pending')

        self.client.force_login(self.me)
        html = self.client.get(reverse('bids:my_bids')).content.decode()
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertNotIn('href="/offers/1/action/withdraw/"', html)
