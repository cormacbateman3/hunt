"""10.21 — the member's home state is the global default, not Pennsylvania.

Every surface that used to open on the hardcoded site default opens on the
viewer's own ``home_state``; the ``is_primary_default`` state is only for
strangers and members who never said one. The home *county* prefills
nothing — it is who the member is, not where a search should start.
"""

from django.contrib.auth.models import AnonymousUser, User
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from apps.core.defaults import default_state
from apps.core.models import GeographicUnit, State


class HomeStateBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'is_primary_default': True})
        cls.md, _ = State.objects.get_or_create(
            code='MD', defaults={'name': 'Maryland', 'slug': 'maryland',
                                 'min_license_year': 1916})
        cls.baltimore = GeographicUnit.objects.create(
            state=cls.md, name='Baltimore', slug='hs-baltimore')
        cls.marylander = User.objects.create_user('hs_marylander', password='pw')
        cls.marylander.profile.home_state = cls.md
        cls.marylander.profile.save(update_fields=['home_state'])
        cls.undeclared = User.objects.create_user('hs_undeclared', password='pw')


class TheHelperTests(HomeStateBase):
    def test_the_home_state_wins(self):
        self.assertEqual(default_state(self.marylander), self.md)

    def test_a_stranger_gets_the_site_default(self):
        self.assertEqual(default_state(AnonymousUser()), self.pa)
        self.assertEqual(default_state(None), self.pa)

    def test_a_member_who_never_said_gets_the_site_default(self):
        self.assertEqual(default_state(self.undeclared), self.pa)


class TheFiltersOpenAtHomeTests(HomeStateBase):
    def test_the_market_bar_opens_on_the_home_state(self):
        self.client.force_login(self.marylander)
        resp = self.client.get(reverse('hunt'))
        self.assertEqual(resp.context['selected_state'], self.md)
        self.assertEqual(resp.context['filters']['state_id'], str(self.md.pk))

    def test_signed_out_the_market_bar_keeps_the_site_default(self):
        resp = self.client.get(reverse('hunt'))
        self.assertEqual(resp.context['selected_state'], self.pa)

    def test_an_explicit_choice_beats_home(self):
        self.client.force_login(self.marylander)
        resp = self.client.get(reverse('hunt'), {'state_id': self.pa.pk})
        self.assertEqual(resp.context['selected_state'], self.pa)

    def test_everything_owned_opens_on_the_home_state(self):
        from apps.collections.browse import page
        context = page(QueryDict(''), self.marylander)
        self.assertEqual(context['filters']['state_id'], str(self.md.pk))

    def test_an_explicit_anywhere_survives(self):
        """An empty ``state_id`` means *anywhere*, home state or not."""
        from apps.collections.browse import resolve_state
        _default, selected = resolve_state(QueryDict('state_id='), self.marylander)
        self.assertIsNone(selected)

    def test_the_map_opens_on_home_ground(self):
        self.client.force_login(self.marylander)
        resp = self.client.get(reverse('hunt_map'))
        self.assertEqual(resp.context['gm_state'], 'MD')

    def test_the_field_guide_button_names_home(self):
        self.client.force_login(self.marylander)
        resp = self.client.get(reverse('almanac'))
        self.assertEqual(resp.context['default_state'], self.md)


class TheFormsOpenAtHomeTests(HomeStateBase):
    def test_a_fresh_listing_form_offers_home(self):
        from apps.listings.forms import ListingForm
        form = ListingForm(user=self.marylander)
        self.assertEqual(form.fields['state'].initial, self.md)
        self.assertIn(self.baltimore, form.fields['county_ref'].queryset)

    def test_a_fresh_shelf_form_offers_home(self):
        from apps.collections.forms import CollectionItemForm
        form = CollectionItemForm(user=self.marylander)
        self.assertEqual(form.fields['state'].initial, self.md)
        self.assertIn(self.baltimore, form.fields['county'].queryset)

    def test_a_member_who_never_said_still_chooses(self):
        from apps.collections.forms import CollectionItemForm
        form = CollectionItemForm(user=self.undeclared)
        self.assertIsNone(form.fields['state'].initial)

    def test_a_posted_clearing_stays_cleared(self):
        """A bound form whose POST omitted the state must not have home
        quietly written back in — the querysets stay empty."""
        from apps.listings.forms import ListingForm
        form = ListingForm(data={'listing_type': 'buy_now'}, user=self.marylander)
        self.assertEqual(form.fields['county_ref'].queryset.count(), 0)

    def test_a_fresh_want_offers_home(self):
        from apps.collections.forms import WantedItemForm
        form = WantedItemForm(user=self.marylander)
        self.assertEqual(form.fields['state'].initial, self.md)
        self.assertIn(self.baltimore, form.fields['county'].queryset)

    def test_the_want_starter_speaks_home(self):
        from apps.collections import wants
        rows = wants.starters(self.marylander)
        self.assertTrue(
            any(f'state_id={self.md.pk}' in row['query'] for row in rows))


class TheEmptyShelfSpeaksHomeTests(HomeStateBase):
    def test_primary_state_falls_back_to_home(self):
        """An empty shelf used to reach for a profile field that has never
        existed and always landed on Pennsylvania."""
        from apps.accounts.views import _primary_state
        self.assertEqual(_primary_state(self.marylander), self.md)
