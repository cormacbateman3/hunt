"""15b — on a phone (Pass 10).

Four tabs at the bottom, and the desk work — settings rooms, the trade
composer, the matrix — hands the page to one honest line instead of a
cramped version nobody uses. The swap itself is CSS (640px and below);
what a Django test can hold down is that the pieces are in the DOM on
the right pages and nowhere near anonymous visitors.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import CollectionItem
from apps.core.models import GeographicUnit, State


class OnAPhoneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('ph_me', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True, 'min_license_year': 1913},
        )
        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='ph-cameron', fips_code='42023')

    def test_a_member_gets_the_four_tabs(self):
        self.client.force_login(self.me)
        resp = self.client.get(reverse('bench'))
        self.assertContains(resp, 'kb-tabbar')
        for label in ('Hunt', 'Mine', 'Bench', 'Add'):
            self.assertContains(resp, label)

    def test_a_visitor_gets_no_tab_bar(self):
        resp = self.client.get(reverse('hunt'))
        self.assertNotContains(resp, 'kb-tabbar')

    def test_the_phone_stylesheet_rides_every_page(self):
        resp = self.client.get(reverse('hunt'))
        self.assertContains(resp, 'mobile.css')

    def test_the_settings_rooms_carry_the_desk_note(self):
        self.client.force_login(self.me)
        resp = self.client.get(reverse('accounts:profile_edit'))
        self.assertContains(resp, 'kb-desk-note')
        self.assertContains(resp, 'open it on a computer')

    def test_the_matrix_carries_the_desk_note(self):
        CollectionItem.objects.create(
            owner=self.me, title='1949 Cameron', state=self.pa,
            county=self.cameron, license_year=1949, condition_grade='good')
        self.client.force_login(self.me)
        resp = self.client.get(
            reverse('collections:my_collection') + '?view=matrix')
        self.assertContains(resp, 'kb-desk-note')
        self.assertContains(resp, 'mn-panel')
