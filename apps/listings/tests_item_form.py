"""The item form against the turn 6b frame — the facts a test can hold.

Tests cannot see layout, so these pin what the drawing writes in words:
the named slots, the panel eyebrows, the human field labels, the chip
ladder, and the footer's promise. The render-and-read step covers the
geometry; this keeps anybody from quietly renaming the furniture.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Address
from apps.core.models import State


class ItemFormBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('if_seller', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )
        address = Address.objects.create(
            user=cls.seller, full_name='Seller', line1='1 Main St',
            city='Williamsport', state='PA', postal_code='17701')
        profile = cls.seller.profile
        profile.shipping_address = address
        profile.save()

    def setUp(self):
        self.client.force_login(self.seller)


class TheStepTwoDrawingTests(ItemFormBase):
    def _page(self, to='auction'):
        return self.client.get(reverse('listings:create') + f'?to={to}')

    def test_the_evidence_rail_and_the_work_share_the_floor(self):
        resp = self._page()
        self.assertContains(resp, 'if-floor')
        self.assertContains(resp, 'if-rail')
        self.assertContains(resp, 'if-work')

    def test_the_named_slots_are_named(self):
        # Captions are 4a's (the newer refinement of 6b's card); the detail
        # caption is 6b's own line. The Turn-5 "fixed slots" copy is retired.
        resp = self._page()
        self.assertContains(resp, 'Featured &middot; front')
        self.assertContains(resp, 'The one buyers see first')
        self.assertContains(resp, 'Pin, printing, stamps')
        self.assertContains(resp, 'data-slot="detail2"')
        self.assertContains(resp, 'Drag to reorder these three')
        self.assertNotContains(resp, 'Front and back are fixed slots')

    def test_the_three_rail_panels_carry_their_eyebrows(self):
        resp = self._page()
        self.assertContains(resp, 'Photographs')
        self.assertContains(resp, 'Read from your photograph')
        self.assertContains(resp, 'tap any line to change it')
        self.assertContains(resp, 'How buyers will see it')

    def test_the_taxonomy_is_out_of_the_drawer_with_human_names(self):
        resp = self._page()
        self.assertContains(resp, 'The detail collectors filter on')
        for label in ('Who it was for', 'What it allowed', 'How long it lasted',
                      'Tags or stamps on it', 'What it’s made of', 'Issue class'):
            self.assertContains(resp, label)
        # The drawer itself is gone from the listing form.
        self.assertNotContains(resp, 'Item taxonomy')

    def test_the_condition_ladder_has_no_blank_rung(self):
        resp = self._page()
        self.assertContains(resp, 'chip-radios')
        self.assertNotContains(resp, '---------')

    def test_tags_still_attached_speaks_person(self):
        resp = self._page()
        self.assertContains(resp, 'Tags still attached?')
        self.assertContains(resp, 'Yes, uncut')
        self.assertContains(resp, 'Not sure')

    def test_the_footer_offers_the_terms_and_the_draft(self):
        # Turn 6b: step 2 never publishes. Its foot points at step 3 and
        # offers the way out — the publish CTA lives on the terms page.
        for to in ('auction', 'buy_now'):
            resp = self._page(to)
            self.assertContains(resp, 'Set the terms')
            self.assertContains(resp, 'Save and come back to it')
            self.assertContains(resp, 'Nothing is public until step 3 is done.')
            self.assertNotContains(resp, 'Put it up for auction')
            self.assertNotContains(resp, 'Starting price')

    def test_material_carries_the_one_hint_the_photograph_cannot_give(self):
        resp = self._page()
        self.assertContains(resp, 'a photograph can&rsquo;t feel card from celluloid')

    def test_condition_writes_as_well_as_grades(self):
        # Turn 6b: the grade filters; the written description stops
        # disputes; Restored sits apart from the ladder, not on it.
        resp = self._page()
        self.assertContains(resp, 'Condition description')
        self.assertContains(resp, 'name="condition_description"')
        self.assertContains(resp, 'if-cond-divider')
        self.assertContains(resp, 'name="is_restored"')
        self.assertContains(resp, 'isn&rsquo;t a rung')
