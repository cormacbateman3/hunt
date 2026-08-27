"""The My-collection destination through the one add flow.

Turn 6: the third card leads to the same step 2 (the item form, wearing
the collection destination) and then to the collection panel — who sees
it, whether it sits in the case, what you'd take for it, and the block
only the owner ever sees. Nothing about money publicly.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import GeographicUnit, State

from .models import MAX_FEATURED, CollectionItem


class CollectionTermsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('ct_owner', password='pw')
        cls.other = User.objects.create_user('ct_other', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913, 'is_primary_default': True},
        )
        cls.sullivan, _ = GeographicUnit.objects.get_or_create(
            state=cls.pa, name='Sullivan',
            defaults={'unit_type': 'County', 'fips_code': '42113'},
        )
        cls.tioga, _ = GeographicUnit.objects.get_or_create(
            state=cls.pa, name='Tioga',
            defaults={'unit_type': 'County', 'fips_code': '42117'},
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def _item(self, **overrides):
        fields = dict(owner=self.owner, title='A 1955 Sullivan',
                      state=self.pa, county=self.sullivan, license_year=1955)
        fields.update(overrides)
        return CollectionItem.objects.create(**fields)


class TheDoorTests(CollectionTermsBase):
    def test_the_collection_card_is_a_real_door_now(self):
        resp = self.client.get(reverse('listings:sell_start'))
        self.assertContains(resp, reverse('collections:create'))

    def test_the_old_query_string_still_arrives(self):
        resp = self.client.get(reverse('listings:create') + '?to=collection')
        self.assertRedirects(resp, reverse('collections:create'))

    def test_step_two_wears_the_destination(self):
        # The destination reads from the band rail and the breadcrumb —
        # the invented page lede ("Going to your collection…") is gone,
        # because 6b/4a start straight into the floor.
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'My collection')
        self.assertContains(resp, 'sl-bandsteps')
        self.assertContains(resp, 'Set the terms')
        self.assertContains(resp, 'Save and come back to it')
        self.assertContains(resp, 'Cancel')
        # Step 3's questions are step 3's, not this page's.
        self.assertNotContains(resp, 'Show it on my profile')
        self.assertNotContains(resp, 'What you paid')

    def test_saving_walks_to_the_collection_panel(self):
        resp = self.client.post(reverse('collections:create'), {
            'item_kind': 'license', 'title': 'A 1955 Sullivan',
            'description': '', 'state': str(self.pa.id),
            'county': str(self.sullivan.id), 'license_year': '1955',
            'shape': 'rectangle', 'resident_status': 'unknown',
            'images-TOTAL_FORMS': '0', 'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0', 'images-MAX_NUM_FORMS': '12',
        })
        item = CollectionItem.objects.get(title='A 1955 Sullivan')
        self.assertRedirects(resp, reverse('collections:item_terms', args=[item.pk]))
        # The panel's questions kept their defaults — public, open to trade.
        self.assertTrue(item.is_public)
        self.assertEqual(item.tradeability, 'open')


class ThePanelTests(CollectionTermsBase):
    def test_the_panel_asks_its_own_questions(self):
        item = self._item()
        resp = self.client.get(reverse('collections:item_terms', args=[item.pk]))
        self.assertContains(resp, 'Show it on my profile')
        self.assertContains(resp, 'Put it in the display case')
        self.assertContains(resp, 'I&rsquo;d consider trading it')
        self.assertContains(resp, 'Only you ever see this')
        self.assertContains(resp, 'What you paid')
        self.assertContains(resp, 'Add it to my collection')

    def test_somebody_else_is_turned_away(self):
        item = self._item()
        self.client.force_login(self.other)
        resp = self.client.get(reverse('collections:item_terms', args=[item.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_the_answers_land_on_the_piece(self):
        item = self._item()
        self.client.post(reverse('collections:item_terms', args=[item.pk]), {
            'featured': 'on',
            'trade_wants': 'Anything pre-1930.',
            'open_to_trade': 'on',
            'purchase_price': '210.00',
            'acquired_note': 'Mar 2026, Bloomsburg',
            'private_note': 'Ask Dale about the overprint.',
        })
        item.refresh_from_db()
        self.assertFalse(item.is_public)   # the toggle was off in this post
        self.assertTrue(item.featured)
        self.assertEqual(item.tradeability, 'open')
        self.assertEqual(str(item.purchase_price), '210.00')
        self.assertEqual(item.acquired_note, 'Mar 2026, Bloomsburg')

    def test_the_display_case_holds_six(self):
        for i in range(MAX_FEATURED):
            self._item(title=f'Cased {i}', featured=True, county=self.tioga)
        item = self._item()
        resp = self.client.post(reverse('collections:item_terms', args=[item.pk]), {
            'is_public': 'on', 'featured': 'on',
        })
        item.refresh_from_db()
        self.assertFalse(item.featured)
        self.assertContains(resp, 'take one out first')

    def test_the_first_of_a_county_says_which_gap_it_closes(self):
        item = self._item()
        resp = self.client.get(reverse('collections:item_terms', args=[item.pk]))
        self.assertContains(resp, 'This closes your Sullivan gap')

    def test_a_second_of_the_same_county_stays_quiet(self):
        self._item(title='The first Sullivan')
        item = self._item(title='The second Sullivan')
        resp = self.client.get(reverse('collections:item_terms', args=[item.pk]))
        self.assertNotContains(resp, 'closes your Sullivan gap')
