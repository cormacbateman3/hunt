"""Backtag — the rename, the routes, Research, and the hero (plan §1–§3).

The URL *names* deliberately kept their old words (hunt, bench, almanac)
— hundreds of reverses and sent letters point at them; only the paths
and the labels people see changed.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class RoutesTests(TestCase):
    def test_the_new_paths_are_the_real_ones(self):
        self.assertEqual(reverse('hunt'), '/market/')
        self.assertEqual(reverse('bench'), '/dashboard/')
        self.assertEqual(reverse('research'), '/research/')
        self.assertEqual(reverse('almanac'), '/research/field-guide/')
        self.assertEqual(reverse('archives'), '/research/archives/')

    def test_the_old_paths_redirect_permanently(self):
        for old, new in (('/hunt/', '/market/'),
                         ('/bench/', '/dashboard/'),
                         ('/almanac/', '/research/field-guide/')):
            resp = self.client.get(old)
            self.assertEqual(resp.status_code, 301, old)
            self.assertEqual(resp.headers['Location'], new)

    def test_old_query_strings_survive_the_redirect(self):
        resp = self.client.get('/hunt/?tab=ending')
        self.assertEqual(resp.headers['Location'], '/market/?tab=ending')


class ResearchTests(TestCase):
    def test_the_landing_offers_its_two_rooms(self):
        resp = self.client.get(reverse('research'))
        self.assertContains(resp, 'The Field Guide')
        self.assertContains(resp, 'The Archives')

    def test_the_archives_shell_says_what_it_is(self):
        resp = self.client.get(reverse('archives'))
        self.assertContains(resp, 'permanent census')
        # The search ships disabled rather than pretending to work.
        self.assertContains(resp, 'disabled')

    def test_the_field_guide_wears_its_new_name(self):
        resp = self.client.get(reverse('almanac'))
        self.assertContains(resp, 'The Field Guide')


class TheNameTests(TestCase):
    def test_the_old_name_is_gone_from_the_pages(self):
        for url in (reverse('home'), reverse('hunt'), reverse('research')):
            resp = self.client.get(url)
            self.assertNotContains(resp, 'KeystoneBid')
            self.assertContains(resp, 'Backtag')


class HeroTests(TestCase):
    def test_the_three_lines_in_order(self):
        html = self.client.get(reverse('home')).content.decode()
        first = html.index('Nobody collects these to get rich.')
        second = html.index('know what they&rsquo;re looking')
        third = html.index('History isn&rsquo;t going to save itself.')
        self.assertTrue(first < second < third)
        self.assertIn('Join the collection', html)
        self.assertIn('Look around first', html)
        self.assertIn('Sellers pay a commission when something sells.', html)


class TwoBarMastheadTests(TestCase):
    def test_the_strap_and_the_est_line_are_gone(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('kb-masthead-strap', html)
        self.assertNotIn('kb-nameplate-est', html)

    def test_sign_out_lives_only_in_the_avatar_menu(self):
        user = User.objects.create_user('bt_member', password='pw')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('kb-strap-link', html)


class TheMarkTests(TestCase):
    def test_the_tag_mark_is_inline_and_everywhere_it_should_be(self):
        html = self.client.get(reverse('home')).content.decode()
        # 2B: the die-cut tag with the punch hole and 13; inline SVG so
        # it takes the context's colour and the page's Petrona.
        self.assertIn('bt-mark', html)
        self.assertIn('>13</text>', html)

    def test_the_auth_lockup_carries_the_descriptor(self):
        html = self.client.get('/accounts/login/').content.decode()
        self.assertIn('bt-mark', html)
        self.assertIn('Collect &middot; Record &middot; Preserve', html)
        self.assertNotIn('Est. 2026', html)


class ModernHeaderTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_search_suggest_groups_the_three_kinds(self):
        from apps.core.models import GeographicUnit, State

        state, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania'})
        GeographicUnit.objects.create(
            state=state, name='Cameron', slug='mh-cameron', fips_code='42023')
        User.objects.create_user('cameron_kid', password='pw')

        data = self.client.get('/api/search/?q=camer').json()
        self.assertEqual(sorted(data.keys()),
                         ['collectors', 'counties', 'listings'])
        self.assertTrue(any('Cameron' in row['title'] for row in data['counties']))
        self.assertTrue(any(row['meta'] == 'cameron_kid' for row in data['collectors']))

    def test_short_queries_stay_quiet(self):
        data = self.client.get('/api/search/?q=c').json()
        self.assertEqual(data, {'listings': [], 'collectors': [], 'counties': []})

    def test_the_badge_is_neutral_until_action_is_required(self):
        from apps.notifications.models import Notification

        member = User.objects.create_user('mh_member', password='pw')
        self.client.force_login(member)
        Notification.objects.create(
            user=member, notification_type='new_message', message='hello')
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertIn('kb-alert-count--brass', html)

        Notification.objects.create(
            user=member, notification_type='order_paid', message='ship it')
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertIn('kb-alert-count--rust', html)

    def test_the_dashboard_dot_marks_something_waiting(self):
        member = User.objects.create_user('mh_dot', password='pw')
        self.client.force_login(member)
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertNotIn('kb-dest-dot', html)
