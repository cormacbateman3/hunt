"""W1.23 — the rules a review has to pass before it lands on a profile.

``tests_card.py`` checks the card against the turn 9b drawing. These check
what the views and the model enforce: only the two people in a completed
deal may review it, each of them once, about the other one; the answer is
one of three words (Good / Middling / Poor, Pass 8); the line is optional and
at most 255 characters; and a stranger is turned away.

Every POST below is the one the card's form sends: ``sentiment`` and
``body`` (csrf is not enforced by the test client).

The trade view redirects with the wrong URL keyword (``pk`` for
``trade_id``) and so fails on every path past the permission check. Trade
rule tests therefore read the outcome from the database with
``raise_request_exception`` off; the redirect itself is pinned by an
``@expectedFailure`` test.
"""

from decimal import Decimal
from unittest import expectedFailure

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.listings.models import Listing
from apps.orders.models import Order
from apps.reviews.forms import ReviewForm
from apps.reviews.models import Review
from apps.trades.models import Trade


class ReviewRulesBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('rr_seller', password='pw')
        cls.buyer = User.objects.create_user('rr_buyer', password='pw')
        cls.outsider = User.objects.create_user('rr_outsider', password='pw')
        cls.order = cls._make_order('completed')

    @classmethod
    def _make_order(cls, status):
        listing = Listing.objects.create(
            seller=cls.seller, listing_type='buy_now', title='1952 Bucks Resident',
            description='d', condition_grade='good', buy_now_price=Decimal('40'),
            status='sold')
        return Order.objects.create(
            listing=listing, buyer=cls.buyer, seller=cls.seller, order_type='buy_now',
            status=status, item_amount=Decimal('40.00'), total_amount=Decimal('45.00'))

    def _review_order(self, user, order=None, follow=False, **data):
        self.client.force_login(user)
        payload = {'sentiment': 'positive', 'body': 'Packed flat between card.'}
        payload.update(data)
        return self.client.post(
            reverse('reviews:submit_order', args=[(order or self.order).pk]),
            payload, follow=follow)


# ── Who may review an order ──────────────────────────────────────────────

class OrderReviewWhoTests(ReviewRulesBase):
    def test_the_buyer_reviews_the_seller(self):
        resp = self._review_order(self.buyer)
        self.assertRedirects(resp, reverse('orders:detail', args=[self.order.pk]),
                             fetch_redirect_response=False)

        review = Review.objects.get(order=self.order)
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.reviewed_user, self.seller)
        self.assertEqual(review.sentiment, 'positive')
        self.assertEqual(review.body, 'Packed flat between card.')
        self.assertEqual(review.moderation_state, 'ok')

    def test_the_seller_reviews_the_buyer(self):
        self._review_order(self.seller, body='Paid the same evening.')
        review = Review.objects.get(order=self.order)
        self.assertEqual(review.reviewer, self.seller)
        self.assertEqual(review.reviewed_user, self.buyer)

    def test_each_side_leaves_one_review_of_the_same_deal(self):
        self._review_order(self.buyer)
        self._review_order(self.seller)
        self.assertEqual(Review.objects.filter(order=self.order).count(), 2)
        self.assertEqual(Review.objects.get(reviewer=self.buyer).reviewed_user, self.seller)
        self.assertEqual(Review.objects.get(reviewer=self.seller).reviewed_user, self.buyer)

    def test_a_stranger_is_turned_away(self):
        resp = self._review_order(self.outsider)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_the_post_cannot_choose_who_is_reviewed(self):
        self._review_order(self.buyer, reviewer=self.outsider.pk,
                           reviewed_user=self.outsider.pk, moderation_state='hidden')
        review = Review.objects.get(order=self.order)
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.reviewed_user, self.seller)
        self.assertEqual(review.moderation_state, 'ok')

    def test_signed_out_visitors_are_sent_to_sign_in(self):
        resp = self.client.post(reverse('reviews:submit_order', args=[self.order.pk]),
                                {'sentiment': 'positive'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])
        self.assertFalse(Review.objects.exists())

    def test_a_review_is_only_ever_posted(self):
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('reviews:submit_order', args=[self.order.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_an_order_that_has_not_completed_cannot_be_reviewed(self):
        for status in ('pending_payment', 'paid', 'label_created', 'in_transit',
                       'delivered', 'cancelled', 'refunded'):
            with self.subTest(status=status):
                order = self._make_order(status)
                resp = self._review_order(self.buyer, order=order, follow=True)
                self.assertContains(resp, 'Reviews are only available for completed orders.')
                self.assertFalse(Review.objects.filter(order=order).exists())

    def test_the_card_is_not_offered_before_the_order_completes(self):
        order = self._make_order('delivered')
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('orders:detail', args=[order.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse('reviews:submit_order', args=[order.pk]))


# ── One per deal per side ────────────────────────────────────────────────

class OnePerDealTests(ReviewRulesBase):
    def test_a_second_review_says_so_and_keeps_the_first(self):
        self._review_order(self.buyer, sentiment='positive')
        resp = self._review_order(self.buyer, sentiment='negative', follow=True)
        self.assertContains(resp, 'You have already left a review for this transaction.')
        self.assertEqual(Review.objects.get(reviewer=self.buyer, order=self.order).sentiment,
                         'positive')

    def test_the_database_refuses_a_second_review_of_the_same_order(self):
        Review.objects.create(reviewer=self.buyer, reviewed_user=self.seller,
                              order=self.order, sentiment='positive')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(reviewer=self.buyer, reviewed_user=self.seller,
                                  order=self.order, sentiment='negative')

    def test_the_database_refuses_a_second_review_of_the_same_trade(self):
        trade = Trade.objects.create(initiator=self.seller, counterparty=self.buyer,
                                     status='completed')
        Review.objects.create(reviewer=self.buyer, reviewed_user=self.seller,
                              trade=trade, sentiment='positive')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(reviewer=self.buyer, reviewed_user=self.seller,
                                  trade=trade, sentiment='neutral')

    def test_one_review_per_order_does_not_limit_reviews_of_other_deals(self):
        second = self._make_order('completed')
        self._review_order(self.buyer)
        self._review_order(self.buyer, order=second)
        self.assertEqual(Review.objects.filter(reviewer=self.buyer).count(), 2)


# ── The shape of a review ────────────────────────────────────────────────

class ReviewShapeTests(ReviewRulesBase):
    def test_the_three_answers_are_good_middling_and_poor(self):
        form = ReviewForm()
        self.assertEqual(
            list(form.fields['sentiment'].choices),
            [('positive', 'Good'), ('neutral', 'Middling'), ('negative', 'Poor')])
        for key in ('positive', 'neutral', 'negative'):
            with self.subTest(key=key):
                self.assertTrue(ReviewForm({'sentiment': key, 'body': ''}).is_valid())

    def test_any_other_answer_is_refused_and_the_reason_shown(self):
        resp = self._review_order(self.buyer, sentiment='excellent', follow=True)
        self.assertContains(resp, 'Select a valid choice.')
        self.assertFalse(Review.objects.exists())

    def test_an_answer_is_required(self):
        resp = self._review_order(self.buyer, sentiment='', follow=True)
        self.assertContains(resp, 'This field is required.')
        self.assertFalse(Review.objects.exists())

    def test_the_line_is_optional(self):
        self._review_order(self.buyer, sentiment='neutral', body='')
        review = Review.objects.get(order=self.order)
        self.assertEqual(review.sentiment, 'neutral')
        self.assertEqual(review.body, '')

    def test_a_line_of_255_characters_fits(self):
        self._review_order(self.buyer, body='a' * 255)
        self.assertEqual(len(Review.objects.get(order=self.order).body), 255)

    def test_a_longer_line_is_refused_and_the_reason_shown(self):
        resp = self._review_order(self.buyer, body='a' * 256, follow=True)
        self.assertContains(resp, 'at most 255 characters')
        self.assertFalse(Review.objects.exists())


# ── The profile summary ──────────────────────────────────────────────────

class ReviewSummaryTests(ReviewRulesBase):
    def _review(self, sentiment, state='ok', reviewer=None):
        order = self._make_order('completed')
        return Review.objects.create(
            reviewer=reviewer or self.buyer, reviewed_user=self.seller, order=order,
            sentiment=sentiment, moderation_state=state)

    def test_a_member_with_no_reviews_has_no_percentage(self):
        self.assertEqual(Review.summary_for_user(self.seller),
                         {'total': 0, 'positive_count': 0, 'positive_pct': None})

    def test_the_share_of_good_reviews_is_rounded(self):
        self._review('positive')
        self._review('positive')
        self._review('neutral')
        summary = Review.summary_for_user(self.seller)
        self.assertEqual(summary['total'], 3)
        self.assertEqual(summary['positive_count'], 2)
        self.assertEqual(summary['positive_pct'], 67)

    def test_a_hidden_review_does_not_count_but_a_flagged_one_does(self):
        self._review('positive')
        self._review('negative', state='hidden')
        self._review('negative', state='flagged')
        summary = Review.summary_for_user(self.seller)
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['positive_pct'], 50)

    def test_reviews_a_member_gave_are_not_counted_as_received(self):
        Review.objects.create(reviewer=self.seller, reviewed_user=self.buyer,
                              order=self.order, sentiment='negative')
        self.assertEqual(Review.summary_for_user(self.seller)['total'], 0)


# ── Trades ───────────────────────────────────────────────────────────────

class TradeReviewTests(ReviewRulesBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.trade = Trade.objects.create(
            initiator=cls.seller, counterparty=cls.buyer, status='completed')

    def _review_trade(self, user, trade=None, **data):
        """Posts the card and reads the outcome from the database — the
        redirect afterwards is broken (see the expected failure below)."""
        self.client.force_login(user)
        self.client.raise_request_exception = False
        payload = {'sentiment': 'positive', 'body': 'Fair swap, well packed.'}
        payload.update(data)
        return self.client.post(
            reverse('reviews:submit_trade', args=[(trade or self.trade).pk]), payload)

    def test_a_stranger_is_turned_away(self):
        resp = self._review_trade(self.outsider)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_each_trader_reviews_the_other(self):
        self._review_trade(self.seller)
        self._review_trade(self.buyer, sentiment='neutral')
        self.assertEqual(Review.objects.get(reviewer=self.seller, trade=self.trade).reviewed_user,
                         self.buyer)
        self.assertEqual(Review.objects.get(reviewer=self.buyer, trade=self.trade).reviewed_user,
                         self.seller)

    def test_a_trade_still_in_the_post_cannot_be_reviewed(self):
        for status in ('awaiting_shipments', 'shipped_both', 'delivered_both', 'cancelled'):
            with self.subTest(status=status):
                trade = Trade.objects.create(
                    initiator=self.seller, counterparty=self.buyer, status=status)
                self._review_trade(self.buyer, trade=trade)
                self.assertFalse(Review.objects.filter(trade=trade).exists())

    def test_a_second_review_of_the_same_trade_keeps_the_first(self):
        self._review_trade(self.buyer, sentiment='positive')
        self._review_trade(self.buyer, sentiment='negative')
        self.assertEqual(Review.objects.filter(reviewer=self.buyer, trade=self.trade).count(), 1)
        self.assertEqual(Review.objects.get(reviewer=self.buyer, trade=self.trade).sentiment,
                         'positive')

    def test_a_longer_line_is_refused(self):
        self._review_trade(self.buyer, body='a' * 256)
        self.assertFalse(Review.objects.filter(trade=self.trade).exists())

    @expectedFailure  # Bug: apps/reviews/views.py redirects with pk= but the URL takes trade_id.
    def test_after_reviewing_a_trade_you_land_back_on_the_trade(self):
        resp = self._review_trade(self.buyer)
        self.assertRedirects(resp, reverse('trades:trade_detail', args=[self.trade.pk]),
                             fetch_redirect_response=False)
