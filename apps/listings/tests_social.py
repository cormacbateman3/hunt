"""10.25 — the honest numbers on a lot: favorites, views, the Listed date.

Three rules under test. The Listed date is when it went up, never when it
was drafted (the leak the intake warned about). A view is one stranger's
session, not a refresh and never the seller. The favourite count wears the
plain word "favorites" and the cards carry the corner heart.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.template import defaultfilters
from django.urls import reverse
from django.utils import timezone

from apps.collections.models import CollectionItem
from apps.favorites.models import Favorite
from apps.listings.models import Listing
from apps.listings.tests_terms import TermsBase


class SocialBase(TermsBase):
    def _live(self):
        draft = self._draft('buy_now')
        Listing.objects.filter(pk=draft.pk).update(
            status='active', buy_now_price=Decimal('50'),
            published_at=timezone.now())
        draft.refresh_from_db()
        return draft


class ListedDateTests(SocialBase):
    def _publish(self, draft):
        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'starting_price': '40', 'duration_days': '7', 'bid_increment': '5',
        })
        draft.refresh_from_db()
        return draft

    def test_publishing_stamps_the_moment_it_went_up(self):
        draft = self._draft('auction')
        Listing.objects.filter(pk=draft.pk).update(
            created_at=timezone.now() - timedelta(days=200))
        draft = self._publish(draft)
        self.assertEqual(draft.status, 'active')
        self.assertIsNotNone(draft.published_at)
        self.assertGreater(
            draft.published_at, timezone.now() - timedelta(minutes=1))

    def test_the_page_says_when_it_went_up_not_when_it_was_drafted(self):
        """A piece catalogued in winter and listed today must not read as
        listed last winter."""
        old = timezone.now() - timedelta(days=200)
        draft = self._draft('auction')
        Listing.objects.filter(pk=draft.pk).update(created_at=old)
        draft = self._publish(draft)

        self.client.logout()
        html = self.client.get(
            reverse('listings:detail', args=[draft.pk])).content.decode()
        stamped = defaultfilters.date(
            timezone.localtime(draft.published_at), 'M j')
        drafted = defaultfilters.date(timezone.localtime(old), 'M j')
        self.assertIn(f'Listed {stamped}', html)
        self.assertNotIn(f'Listed {drafted}', html)

    def test_the_activation_job_stamps_the_scheduled(self):
        draft = self._draft('buy_now')
        Listing.objects.filter(pk=draft.pk).update(
            status='scheduled', buy_now_price=Decimal('50'),
            scheduled_at=timezone.now() - timedelta(minutes=5))
        call_command('activate_scheduled_listings')
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'active')
        self.assertIsNotNone(draft.published_at)
        self.assertGreater(
            draft.published_at, timezone.now() - timedelta(minutes=1))

    def test_a_relist_is_freshly_listed_and_unseen(self):
        """The relist clones the row — the clone must not inherit last
        week's Listed date or another lot's view count."""
        from apps.bids.services import close_auction

        listing = self._draft('auction')
        Listing.objects.filter(pk=listing.pk).update(
            status='active', starting_price=Decimal('40'),
            published_at=timezone.now() - timedelta(days=7), view_count=41,
            auction_end=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        close_auction(listing)

        relist = Listing.objects.filter(original_listing=listing).first()
        self.assertIsNotNone(relist)
        self.assertEqual(relist.view_count, 0)
        self.assertGreater(
            relist.published_at, timezone.now() - timedelta(minutes=1))


class ViewCountTests(SocialBase):
    def test_a_stranger_counts_once_per_session(self):
        lot = self._live()
        self.client.force_login(self.buyer)
        self.client.get(reverse('listings:detail', args=[lot.pk]))
        self.client.get(reverse('listings:detail', args=[lot.pk]))
        lot.refresh_from_db()
        self.assertEqual(lot.view_count, 1)

    def test_the_sellers_own_visits_count_for_nothing(self):
        lot = self._live()
        self.client.get(reverse('listings:detail', args=[lot.pk]))
        lot.refresh_from_db()
        self.assertEqual(lot.view_count, 0)

    def test_a_visitor_with_no_account_still_counts(self):
        lot = self._live()
        self.client.logout()
        self.client.get(reverse('listings:detail', args=[lot.pk]))
        lot.refresh_from_db()
        self.assertEqual(lot.view_count, 1)

    def test_the_page_wears_the_plain_words(self):
        lot = self._live()
        Favorite.objects.create(user=self.buyer, listing=lot)
        self.client.force_login(self.buyer)
        html = self.client.get(
            reverse('listings:detail', args=[lot.pk])).content.decode()
        self.assertIn('1 view', html)
        self.assertIn('1 favorite', html)


class CardHeartTests(SocialBase):
    def test_the_market_card_carries_the_heart_and_the_count(self):
        lot = self._live()
        Favorite.objects.create(user=self.buyer, listing=lot)
        self.client.force_login(self.buyer)
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertIn('kb-card-watch is-on', html)
        self.assertIn('1 favorite', html)

    def test_a_stranger_is_walked_to_the_door(self):
        self._live()
        self.client.logout()
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertIn('kb-card-watch', html)
        self.assertIn(reverse('accounts:login'), html)

    def test_the_sellers_own_card_offers_no_heart(self):
        """Saving your own lot is noise — the seller sees counts, not a
        button, on their own cards."""
        self._live()
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertNotIn('kb-card-watch', html)

    def test_the_shelf_grid_carries_hearts_too(self):
        item = CollectionItem.objects.create(
            owner=self.seller, title='1949 Cameron shelf piece', state=self.pa,
            is_public=True, condition_grade='good')
        Favorite.objects.create(user=self.buyer, collection_item=item)
        self.client.force_login(self.buyer)
        html = self.client.get(
            reverse('collectors') + '?tab=owned').content.decode()
        self.assertIn('kb-card-watch is-on', html)
        self.assertIn('1 favorite', html)

    def test_the_item_detail_counts_favorites_out_loud(self):
        item = CollectionItem.objects.create(
            owner=self.seller, title='1950 Fulton shelf piece', state=self.pa,
            is_public=True, condition_grade='good')
        Favorite.objects.create(user=self.buyer, collection_item=item)
        self.client.force_login(self.buyer)
        html = self.client.get(
            reverse('collections:item_detail', args=[item.pk])).content.decode()
        self.assertIn('1 favorite', html)
