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
