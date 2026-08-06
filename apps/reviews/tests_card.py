"""The review card against the turn 9b frame.

Three options with a line describing the deal each one fits, a 255-character
line with a counter, one dark button, and a footnote that draws the line
between a poor review and an actual complaint. One review per deal per side,
and it stands as written.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import State
from apps.listings.models import Listing
from apps.orders.models import Order
from apps.reviews.models import Review


class ReviewCardBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('rv_seller', password='pw')
        profile = cls.seller.profile
        profile.display_name = 'Tom Brenneman'
        profile.save()
        cls.buyer = User.objects.create_user('rv_buyer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )
        cls.listing = Listing.objects.create(
            seller=cls.seller, title='1949 Tioga Resident', description='d',
            state=cls.pa, license_year=1949, condition_grade='good',
            listing_type='buy_now', buy_now_price='40.00', status='sold',
        )
        cls.order = Order.objects.create(
            buyer=cls.buyer, seller=cls.seller, listing=cls.listing,
            order_type='buy_now', status='completed',
            item_amount=Decimal('40.00'), shipping_amount=Decimal('5.00'),
            platform_fee_amount=Decimal('2.00'), total_amount=Decimal('47.00'),
        )

    def _order_page(self):
        return self.client.get(reverse('orders:detail', args=[self.order.pk]))


class TheCardDrawingTests(ReviewCardBase):
    def test_the_words_are_good_middling_poor(self):
        review = Review.objects.create(
            reviewer=self.buyer, reviewed_user=self.seller,
            order=self.order, sentiment='positive')
        self.assertEqual(review.get_sentiment_display(), 'Good')
        review.sentiment = 'neutral'
        self.assertEqual(review.get_sentiment_display(), 'Middling')
        review.sentiment = 'negative'
        self.assertEqual(review.get_sentiment_display(), 'Poor')

    def test_the_buyer_sees_the_card_asking_about_the_seller(self):
        self.client.force_login(self.buyer)
        resp = self._order_page()
        self.assertContains(resp, 'How was Tom Brenneman to deal with?')
        self.assertContains(resp, 'One review per deal, from each side.')
        self.assertContains(resp, 'I&rsquo;d deal with them again')
        self.assertContains(resp, 'Described it right, packed it well, sent it on time')
        self.assertContains(resp, 'It got here, but something wasn&rsquo;t right')
        self.assertContains(resp, 'I&rsquo;d think twice next time')
        self.assertContains(resp, 'A line about it')
        self.assertContains(resp, '0 / 255')
        self.assertContains(resp, 'Leave it')
        self.assertContains(resp, 'a review isn&rsquo;t a complaint')

    def test_the_seller_reviewing_the_buyer_reads_buyer_lines(self):
        self.client.force_login(self.seller)
        resp = self._order_page()
        self.assertContains(resp, 'Paid on time, easy to deal with')
        self.assertNotContains(resp, 'packed it well')

    def test_no_blank_radio_and_no_old_words(self):
        self.client.force_login(self.buyer)
        resp = self._order_page()
        self.assertNotContains(resp, '---------')
        self.assertNotContains(resp, 'Positive')
        self.assertNotContains(resp, 'Negative')

    def test_helper_names_the_next_reader_and_the_house_rule(self):
        self.client.force_login(self.buyer)
        resp = self._order_page()
        self.assertContains(resp, 'the next buyer')
        self.assertContains(resp, 'Keep people&rsquo;s addresses and prices out of it.')


class ItStandsAsWrittenTests(ReviewCardBase):
    def test_a_left_review_replaces_the_card_with_the_record(self):
        Review.objects.create(
            reviewer=self.buyer, reviewed_user=self.seller,
            order=self.order, sentiment='positive',
            body='Described the foxing exactly.')
        self.client.force_login(self.buyer)
        resp = self._order_page()
        self.assertNotContains(resp, 'Leave it')
        self.assertContains(resp, 'You said <strong>Good</strong>')
        self.assertContains(resp, 'A review stands as written.')

    def test_a_second_submit_is_turned_away(self):
        Review.objects.create(
            reviewer=self.buyer, reviewed_user=self.seller,
            order=self.order, sentiment='positive')
        self.client.force_login(self.buyer)
        self.client.post(
            reverse('reviews:submit_order', args=[self.order.pk]),
            {'sentiment': 'negative', 'body': 'Changed my mind.'})
        review = Review.objects.get(reviewer=self.buyer, order=self.order)
        self.assertEqual(review.sentiment, 'positive')
        self.assertEqual(Review.objects.filter(order=self.order).count(), 1)
