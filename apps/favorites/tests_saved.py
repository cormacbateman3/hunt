"""Saved, and the notification centre — two pages that stopped being chores.

Saved sorts by what closes soonest, not by when you saved it, and keeps what
got away. The centre marks things read by being read.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.models import Bid
from apps.collections.models import CollectionItem
from apps.core.models import State
from apps.favorites import saved
from apps.favorites.models import Favorite
from apps.listings.models import Listing
from apps.notifications import centre
from apps.notifications.models import Notification


class SavedBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('sv_me', password='pw')
        cls.them = User.objects.create_user('sv_them', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def _auction(self, hours, **kwargs):
        listing = Listing.objects.create(
            seller=self.them, title=kwargs.pop('title', 'A lot'), description='d',
            state=self.pa, condition_grade='good', status=kwargs.pop('status', 'active'),
            listing_type='auction', starting_price=Decimal('40'),
            auction_end=timezone.now() + timedelta(hours=hours), **kwargs)
        Favorite.objects.create(user=self.me, listing=listing)
        return listing


class SavedTests(SavedBase):
    def test_soonest_to_close_leads(self):
        self._auction(20, title='Later')
        self._auction(1, title='Tonight')
        self._auction(6, title='Middle')

        titles = [row['listing'].title for row in saved.page(self.me)['watching']]
        self.assertEqual(titles, ['Tonight', 'Middle', 'Later'])

    def test_the_card_says_where_your_bid_stands(self):
        listing = self._auction(4)
        Bid.objects.create(listing=listing, bidder=self.me, amount=Decimal('50'))
        self.assertEqual(saved.page(self.me)['watching'][0]['state'], 'You’re outbid')

        Bid.objects.filter(listing=listing, bidder=self.me).update(is_winning=True)
        self.assertEqual(saved.page(self.me)['watching'][0]['state'], 'You’re ahead')

    def test_a_lot_you_never_bid_on_says_so_without_claiming_otherwise(self):
        listing = self._auction(4)
        stranger = User.objects.create_user('sv_stranger')
        Bid.objects.create(listing=listing, bidder=stranger, amount=Decimal('50'))
        self.assertEqual(saved.page(self.me)['watching'][0]['state'],
                         '1 bid · not your bid')

    def test_the_countdown_is_short_enough_to_sit_on_a_card(self):
        self._auction(4)
        self.assertRegex(saved.page(self.me)['watching'][0]['closes_in'], r'^\dh \d\dm$')

    def test_sold_ones_stay_but_move_out_of_watching(self):
        self._auction(-2, status='sold', title='Got away')
        page = saved.page(self.me)
        self.assertEqual(page['watching'], [])
        self.assertEqual(page['gone'][0]['listing'].title, 'Got away')

    def test_pieces_report_only_what_the_flag_can_carry(self):
        item = CollectionItem.objects.create(
            owner=self.them, title='1913 Lycoming', is_public=True, trade_eligible=True)
        Favorite.objects.create(user=self.me, collection_item=item)
        self.assertTrue(saved.page(self.me)['pieces'][0]['open_to_trades'])

        CollectionItem.objects.filter(pk=item.pk).update(trade_eligible=False)
        self.assertFalse(saved.page(self.me)['pieces'][0]['open_to_trades'])

    def test_the_tab_counts_survive_being_on_another_tab(self):
        self._auction(4)
        item = CollectionItem.objects.create(owner=self.them, title='A piece', is_public=True)
        Favorite.objects.create(user=self.me, collection_item=item)

        counts = {chip['key']: chip['count'] for chip in saved.page(self.me, 'pieces')['tabs']}
        self.assertEqual(counts, {'watching': 1, 'pieces': 1, 'gone': 0})

    def test_the_page_renders_each_tab(self):
        self._auction(4, title='Watch me')
        self.client.force_login(self.me)
        for tab, expected in (('', 'Watch me'), ('pieces', 'No pieces saved'),
                              ('gone', 'Nothing has got away yet')):
            with self.subTest(tab=tab):
                resp = self.client.get(reverse('favorites:list'), {'tab': tab})
                self.assertContains(resp, expected)


class NotificationCentreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('nt_me', password='pw')

    def test_three_dot_states_and_no_more(self):
        self.assertEqual(centre.tone_for('outbid'), 'urgent')
        self.assertEqual(centre.tone_for('offer_received'), 'answer')
        self.assertEqual(centre.tone_for('auction_sold'), 'news')

    def test_reading_the_page_marks_what_is_on_it_read(self):
        note = Notification.objects.create(
            user=self.me, notification_type='outbid', message='You were outbid.')
        self.client.force_login(self.me)

        resp = self.client.get(reverse('notifications:center'))
        # The page still describes what the collector is looking at...
        self.assertEqual(resp.context['unread_here'], 1)
        # ...but it is read by the time they leave.
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_the_second_visit_reports_nothing_unread(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='You were outbid.')
        self.client.force_login(self.me)
        self.client.get(reverse('notifications:center'))
        again = self.client.get(reverse('notifications:center'))
        self.assertEqual(again.context['unread_here'], 0)

    def test_a_row_carries_no_button_it_cannot_honour(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='No link on this one.')
        self.client.force_login(self.me)
        days = self.client.get(reverse('notifications:center')).context['days']
        self.assertEqual(days[0]['rows'][0]['action'], '')

    def test_a_linked_row_gets_the_verb_for_its_kind(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='Outbid.',
            link_url='/listings/1/')
        self.client.force_login(self.me)
        days = self.client.get(reverse('notifications:center')).context['days']
        self.assertEqual(days[0]['rows'][0]['action'], 'Bid again')

    def test_the_per_row_mark_read_form_is_gone(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='Outbid.')
        self.client.force_login(self.me)
        html = self.client.get(reverse('notifications:center')).content.decode()
        self.assertNotIn('mark-read', html)
        self.assertIn('Mark all read', html)

    def test_filters_narrow_by_subject(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='Bidding thing.')
        Notification.objects.create(
            user=self.me, notification_type='order_paid', message='Deal thing.')

        self.client.force_login(self.me)
        resp = self.client.get(reverse('notifications:center'), {'show': 'bidding'})
        self.assertContains(resp, 'Bidding thing.')
        self.assertNotContains(resp, 'Deal thing.')

    def test_days_are_labelled_not_timestamped(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='Today.')
        old = Notification.objects.create(
            user=self.me, notification_type='outbid', message='Before.')
        Notification.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1))

        self.client.force_login(self.me)
        labels = [day['label'] for day in
                  self.client.get(reverse('notifications:center')).context['days']]
        self.assertEqual(labels, ['Today', 'Yesterday'])
