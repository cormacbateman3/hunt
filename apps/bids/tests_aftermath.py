"""After the close: who won, said everywhere somebody would look.

The Settled section answers "did I win?" in Bids & offers; the detail
page tells everyone the outcome (signed out included); the Auction House
keeps a Just-closed strip for 24 hours under the live grid.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.bids.services import close_auction, place_bid
from apps.listings.models import Listing
from apps.orders.models import Order


class AftermathBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name):
            user = User.objects.create_user(name, password='pw')
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.seller = verified('am_seller')
        cls.ann = verified('am_ann')
        cls.bob = verified('am_bob')
        address = Address.objects.create(
            user=cls.seller, full_name='S', line1='1 Rd', city='H',
            state='PA', postal_code='17101', is_default=True)
        cls.seller.profile.shipping_address = address
        cls.seller.profile.save(update_fields=['shipping_address'])

    def _closed_auction(self, winner_max='500', loser_max='100'):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='auction', title='A closed lot',
            description='d', condition_grade='good', status='active',
            starting_price=Decimal('20'), bid_increment=Decimal('5'),
            auction_end=timezone.now() + timedelta(hours=1), auto_relist=False,
        )
        place_bid(listing, self.ann, Decimal(winner_max))
        place_bid(listing, self.bob, Decimal(loser_max))
        Listing.objects.filter(pk=listing.pk).update(
            auction_end=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        close_auction(listing)
        listing.refresh_from_db()
        return listing


class TheSettledTests(AftermathBase):
    def test_the_winner_is_told_to_pay(self):
        self._closed_auction()
        self.client.force_login(self.ann)
        resp = self.client.get(reverse('bids:my_bids'))
        self.assertContains(resp, 'Settled')
        self.assertContains(resp, 'You won it')
        self.assertContains(resp, 'Review &amp; pay')

    def test_the_loser_learns_what_it_went_for(self):
        listing = self._closed_auction()
        self.client.force_login(self.bob)
        resp = self.client.get(reverse('bids:my_bids'))
        self.assertContains(resp, 'Went to someone else')
        self.assertContains(resp, 'Went for')
        self.assertContains(resp, f'${listing.current_bid:.2f}')

    def test_a_paid_win_points_at_the_order(self):
        listing = self._closed_auction()
        Order.objects.filter(listing=listing).update(status='paid')
        self.client.force_login(self.ann)
        resp = self.client.get(reverse('bids:my_bids'))
        self.assertContains(resp, 'View order')


class TheOutcomeBannerTests(AftermathBase):
    def test_a_signed_out_watcher_sees_the_outcome_not_a_login_wall(self):
        listing = self._closed_auction()
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, 'Sold for')
        self.assertContains(resp, 'awaiting the winner')
        self.assertNotContains(resp, 'Sign in to bid')

    def test_the_losing_bidder_sees_the_outcome_on_the_page(self):
        listing = self._closed_auction()
        self.client.force_login(self.bob)
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, 'Sold for')
        self.assertNotContains(resp, 'Place bid')

    def test_the_seller_sees_the_outcome_too(self):
        listing = self._closed_auction()
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, 'Sold for')
        self.assertNotContains(resp, 'You cannot bid on it')


class TheJustClosedTests(AftermathBase):
    def test_the_strip_shows_under_the_auction_format(self):
        listing = self._closed_auction()
        resp = self.client.get(reverse('hunt') + '?format=auction')
        self.assertContains(resp, 'Just closed')
        self.assertContains(resp, 'A closed lot')
        self.assertContains(resp, f'Went for ${listing.current_bid:.2f}')

    def test_the_strip_stays_out_of_the_general_hunt(self):
        self._closed_auction()
        resp = self.client.get(reverse('hunt'))
        self.assertNotContains(resp, 'Just closed')

    def test_old_closes_age_out(self):
        listing = self._closed_auction()
        Listing.objects.filter(pk=listing.pk).update(
            auction_end=timezone.now() - timedelta(hours=30))
        resp = self.client.get(reverse('hunt') + '?format=auction')
        self.assertNotContains(resp, 'Just closed')

    def test_an_unsold_close_is_told_plainly(self):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='auction', title='Nobody came',
            description='d', condition_grade='good', status='active',
            starting_price=Decimal('20'),
            auction_end=timezone.now() - timedelta(minutes=1), auto_relist=False,
        )
        close_auction(listing)
        resp = self.client.get(reverse('hunt') + '?format=auction')
        self.assertContains(resp, 'Didn&rsquo;t sell')
