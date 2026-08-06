"""Questions on a listing, against the turn 9b frame.

The three rules the drawing carries: answers sit under questions with the
seller marked in brass, an unanswered question is visibly waiting, and price
talk is hidden the moment it is asked — shown only to its asker with the
explanation in place, never to the seller, never to the room.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import State
from apps.listings import qa
from apps.listings.models import Listing, ListingQuestion
from apps.notifications.models import Notification


class QABase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('qa_seller', password='pw')
        profile = cls.seller.profile
        profile.display_name = 'Harold Kreider'
        profile.save()
        cls.buyer = User.objects.create_user('qa_buyer', password='pw')
        buyer_profile = cls.buyer.profile
        buyer_profile.display_name = 'Moses Yoder'
        buyer_profile.save()
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )
        cls.listing = Listing.objects.create(
            seller=cls.seller, title='1949 Tioga Resident', description='d',
            state=cls.pa, license_year=1949, condition_grade='good',
            listing_type='buy_now', buy_now_price='40.00', allow_offers=True,
            status='active',
        )

    def _detail(self):
        return self.client.get(reverse('listings:detail', args=[self.listing.pk]))

    def _ask(self, text):
        return self.client.post(
            reverse('listings:ask_question', args=[self.listing.pk]),
            {'question': text},
        )


class PriceTalkTests(QABase):
    def test_the_haggling_openers_are_recognised(self):
        for opener in ('Would you take $150 for it?',
                       'will you take 80 bucks',
                       'What is the lowest you would go?',
                       'Best offer gets it?'):
            self.assertTrue(qa.is_price_talk(opener), opener)

    def test_a_real_question_is_not_price_talk(self):
        for honest in ('Is the pin original to the button?',
                       'Any chance of a measurement across the face?',
                       'How many were issued that year?'):
            self.assertFalse(qa.is_price_talk(honest), honest)

    def test_price_talk_is_hidden_at_the_moment_it_is_asked(self):
        self.client.force_login(self.buyer)
        self._ask('Would you take $150 for it?')
        question = ListingQuestion.objects.get(listing=self.listing)
        self.assertEqual(question.moderation_state, 'hidden')

    def test_the_seller_is_not_notified_of_a_side_deal_opener(self):
        self.client.force_login(self.buyer)
        self._ask('Would you take $150 for it?')
        self.assertFalse(
            Notification.objects.filter(
                user=self.seller, notification_type='listing_question_received',
            ).exists())
        # An honest question still knocks.
        self._ask('Is the pin original?')
        self.assertTrue(
            Notification.objects.filter(
                user=self.seller, notification_type='listing_question_received',
            ).exists())

    def test_the_asker_sees_their_hidden_question_with_the_norm(self):
        self.client.force_login(self.buyer)
        self._ask('Would you take $150 for it?')
        resp = self._detail()
        self.assertContains(resp, 'Would you take $150 for it?')
        self.assertContains(resp, 'Price talk belongs in an offer, not out here.')
        self.assertContains(resp, 'Make an offer instead')
        self.assertContains(resp, 'Hidden')

    def test_nobody_else_sees_it_including_the_seller(self):
        self.client.force_login(self.buyer)
        self._ask('Would you take $150 for it?')

        visitor = User.objects.create_user('qa_visitor', password='pw')
        self.client.force_login(visitor)
        self.assertNotContains(self._detail(), 'Would you take $150')

        self.client.force_login(self.seller)
        self.assertNotContains(self._detail(), 'Would you take $150')

    def test_hidden_questions_stay_out_of_the_asked_count(self):
        self.client.force_login(self.buyer)
        self._ask('Would you take $150 for it?')
        self._ask('Is the pin original?')
        self.assertEqual(qa.asked_count(self.listing), 1)


class TheThreadDrawingTests(QABase):
    def _answered(self, question_text='Is the pin original?', answer='Original, and unbent.'):
        question = ListingQuestion.objects.create(
            listing=self.listing, asker=self.buyer, question=question_text)
        question.seller_answer = answer
        question.answered_at = timezone.now()
        question.save()
        return question

    def test_the_answer_names_the_seller_in_brass(self):
        self._answered()
        resp = self._detail()
        self.assertContains(resp, 'qa-seller')
        self.assertContains(resp, 'Harold Kreider, the seller')
        # And never the old shape.
        self.assertNotContains(resp, '<strong>Seller:</strong>')

    def test_bylines_use_the_short_name_not_the_username(self):
        self._answered()
        resp = self._detail()
        self.assertContains(resp, 'M. Yoder')

    def test_an_unanswered_question_is_visibly_waiting(self):
        ListingQuestion.objects.create(
            listing=self.listing, asker=self.buyer, question='Is the pin original?')
        resp = self._detail()
        self.assertContains(resp, 'waiting on an answer')

    def test_the_head_counts_and_the_ask_box_names_the_seller(self):
        self._answered()
        resp = self._detail()
        self.assertContains(resp, 'Questions about this one')
        self.assertContains(resp, '1 asked')
        self.client.force_login(self.buyer)
        resp = self._detail()
        self.assertContains(resp, 'Ask Harold Kreider something about the item')
        self.assertContains(resp, 'write to them instead')

    def test_the_answer_habit_appears_once_it_is_a_habit(self):
        for i in range(3):
            question = ListingQuestion.objects.create(
                listing=self.listing, asker=self.buyer, question=f'Q{i}?')
            ListingQuestion.objects.filter(pk=question.pk).update(
                created_at=timezone.now() - timedelta(hours=5),
                seller_answer='A.', answered_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(qa.answer_habit(self.seller), 'answers within the day')
        resp = self._detail()
        self.assertContains(resp, 'Harold Kreider answers within the day')

    def test_no_habit_line_before_there_is_a_habit(self):
        self.assertEqual(qa.answer_habit(self.seller), '')
        self.assertNotContains(self._detail(), 'answers within')
