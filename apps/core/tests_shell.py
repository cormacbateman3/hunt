"""The shell — four zones, derived once from the resolved view name.

The design document is ordered newest-first. Turn 1 proposed a three-zone
shell; turn 2a revised it and turns 2-21 all use the revision. These tests
pin the settled answer so it cannot drift back.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import State


class ZoneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('zone_user', password='pw')
        State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def test_each_zone_root_marks_itself_current(self):
        cases = [('hunt', 'hunt'), ('collectors', 'collections'),
                 ('almanac', 'almanac')]
        for url_name, zone in cases:
            with self.subTest(url_name=url_name):
                resp = self.client.get(reverse(url_name))
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.context['kb_zone'], zone)

    def test_bench_is_its_own_zone(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('bench'))
        self.assertEqual(resp.context['kb_zone'], 'bench')

    def test_managing_your_collection_is_bench_not_collections(self):
        """Managing yours is work, so it lives in My Bench. Looking at
        someone else's is discovery, so it lives in Collections."""
        self.client.force_login(self.user)
        mine = self.client.get(reverse('collections:my_collection'))
        self.assertEqual(mine.context['kb_zone'], 'bench')

        theirs = self.client.get(reverse('collections:browse'))
        self.assertEqual(theirs.context['kb_zone'], 'collections')

    def test_a_listing_page_belongs_to_hunt(self):
        resp = self.client.get(reverse('hunt'))
        self.assertEqual(resp.context['kb_zone'], 'hunt')

    def test_the_masthead_carries_all_four_zones_when_signed_in(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('hunt')).content.decode()
        for label in ('>The Market</a>', '>Collections</a>', '>Research</a>',
                      'Dashboard'):
            self.assertIn(label, html)

    def test_signed_out_visitors_are_not_offered_a_dashboard(self):
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertNotIn('Dashboard', html)
        self.assertIn('>Research</a>', html)

    def test_the_username_dropdown_is_gone(self):
        """It hid state. Its items are visible workspace tabs now; the
        avatar carries only profile, settings and sign out."""
        self.client.force_login(self.user)
        html = self.client.get(reverse('hunt')).content.decode()
        self.assertNotIn('user-menu-dropdown', html)
        self.assertIn('kb-account-menu', html)
        for gone in ('>My Listings<', '>Orders<', '>Favorites<'):
            self.assertNotIn(gone, html)


class AlmanacPlaceholderTests(TestCase):
    def test_the_almanac_says_plainly_that_it_is_not_built(self):
        resp = self.client.get(reverse('almanac'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Not built yet')

    def test_it_points_at_something_that_does_exist(self):
        State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        resp = self.client.get(reverse('almanac'))
        self.assertContains(resp, reverse('hunt'))


class SecondStepDialogTests(TestCase):
    """10.24 - one confirm dialog for everything destructive.

    Read the artifacts, not the DOM: the dialog must live once in
    custom.js (with the delegated data-kb-confirm wire-up), and the
    photograph confirm in item-form.js must delegate to it rather than
    carry a second copy that could drift."""

    @staticmethod
    def _js(name):
        from pathlib import Path

        from django.conf import settings
        return (Path(settings.BASE_DIR) / 'static' / 'js' / name).read_text(
            encoding='utf-8')

    def test_custom_js_owns_the_dialog_and_the_wireup(self):
        js = self._js('custom.js')
        self.assertIn('window.kbConfirm', js)
        self.assertIn('data-kb-confirm', js)
        self.assertIn('requestSubmit', js)

    def test_item_form_js_delegates_instead_of_duplicating(self):
        js = self._js('item-form.js')
        self.assertIn('window.kbConfirm', js)
        self.assertNotIn('kb-modal-overlay', js)
