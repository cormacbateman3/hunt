"""Home — the masthead, the bands, and the Day Book.

Turn 2b (signed in) and 2c (signed out). These are deliberately two
different templates, not one page with the greeting switched off.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.daybook import day_book
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing
from apps.notifications.models import Notification


class HomeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('home_seller', password='pw')
        cls.viewer = User.objects.create_user('home_viewer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True, 'issuance_unit_label': 'County'},
        )
        cls.unit = GeographicUnit.objects.create(
            state=cls.pa, name='Lycoming', slug='pa-lycoming')
        common = {
            'seller': cls.seller, 'description': 'd', 'state': cls.pa,
            'county_ref': cls.unit, 'condition_grade': 'good',
            'status': 'active', 'license_year': 1934,
        }
        cls.auction = Listing.objects.create(
            title='1934 Lycoming Resident', listing_type='auction',
            starting_price=Decimal('40'),
            auction_end=timezone.now() + timedelta(hours=3), **common)
        cls.store = Listing.objects.create(
            title='1929 Lycoming Antlerless', listing_type='buy_now',
            buy_now_price=Decimal('265'), allow_offers=True, **common)

    def test_a_stranger_gets_the_signed_out_page(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'home_signed_out.html')
        self.assertTemplateNotUsed(resp, 'home.html')

    def test_a_member_gets_the_signed_in_page(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse('home'))
        self.assertTemplateUsed(resp, 'home.html')
        self.assertTemplateNotUsed(resp, 'home_signed_out.html')

    def test_home_carries_the_full_masthead_and_other_pages_do_not(self):
        """158px on home, compressed to 56px everywhere else (2a)."""
        home = self.client.get(reverse('home')).content.decode()
        self.assertIn('kb-masthead', home)
        # Two bars now (implementation plan §2): the utility strip and
        # the EST. sub-line are gone; the nameplate stands alone.
        self.assertNotIn('kb-masthead-strap', home)
        self.assertNotIn('Est. 2026', home)

        hunt = self.client.get(reverse('hunt')).content.decode()
        self.assertNotIn('kb-masthead', hunt)
        self.assertIn('kb-topbar', hunt)

    def test_the_three_names_are_on_the_goods_not_in_the_nav(self):
        """Turn 2: keep the three names, take them out of the navigation."""
        resp = self.client.get(reverse('home'))
        html = resp.content.decode()
        for name in ('The Auction House', 'The General Store', 'The Trading Block'):
            self.assertIn(name, html)
        # ...and they are not zone links in the masthead nav.
        self.assertNotIn('>The Auction House</a>', html.replace('hm-market-name">', '>'))

    def test_marketplace_strip_counts_each_format(self):
        resp = self.client.get(reverse('home'))
        counts = {m['name']: m['count'] for m in resp.context['marketplaces']}
        self.assertEqual(counts['The Auction House'], 1)
        self.assertEqual(counts['The General Store'], 1)
        self.assertEqual(counts['The Trading Block'], 0)

    def test_greeting_reports_what_needs_you(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.context['needs_count'], 0)
        self.assertContains(resp, 'Nothing needs you')

    def test_signed_out_page_never_greets_or_shows_a_bench(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('hm-greeting-title', html)
        self.assertNotIn('Go to my bench', html)
        self.assertIn('Join the community', html)


class DayBookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('db_me', password='pw')
        cls.them = User.objects.create_user('db_them', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania'},
        )

    def _listing(self, **kwargs):
        defaults = {
            'seller': self.them, 'description': 'd', 'state': self.pa,
            'condition_grade': 'good', 'status': 'active',
            'listing_type': 'buy_now', 'buy_now_price': Decimal('50'),
            'title': 'A licence',
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def test_a_new_listing_writes_a_line(self):
        self._listing(title='1913 Cambria Resident')
        lines = day_book(self.me)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['subject'], 'db_them')
        self.assertIn('1913 Cambria Resident', lines[0]['text'])
        self.assertIn('The General Store', lines[0]['text'])

    def test_your_own_notifications_appear_and_other_peoples_do_not(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='You were outbid.')
        Notification.objects.create(
            user=self.them, notification_type='outbid', message='Not yours.')

        mine = [line['text'] for line in day_book(self.me)]
        self.assertIn('You were outbid.', mine)
        self.assertNotIn('Not yours.', mine)

    def test_an_urgent_notification_is_toned_differently(self):
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='Outbid.')
        line = next(l for l in day_book(self.me) if l['text'] == 'Outbid.')
        self.assertEqual(line['tone'], 'urgent')

    def test_lines_are_newest_first(self):
        self._listing(title='Older')
        self._listing(title='Newer')
        lines = day_book(self.me)
        self.assertGreaterEqual(lines[0]['at'], lines[-1]['at'])

    def test_stale_events_fall_out_of_the_window(self):
        old = self._listing(title='Ancient')
        Listing.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=9))
        self.assertEqual(day_book(self.me), [])

    def test_an_anonymous_visitor_gets_the_site_lines_only(self):
        from django.contrib.auth.models import AnonymousUser
        self._listing(title='Public thing')
        Notification.objects.create(
            user=self.me, notification_type='outbid', message='Private thing.')

        texts = [line['text'] for line in day_book(AnonymousUser())]
        self.assertTrue(any('Public thing' in t for t in texts))
        self.assertNotIn('Private thing.', texts)
