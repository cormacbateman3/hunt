"""10.8 collection-form parity tests: year bounds + addon dimension clearing."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.collections.forms import CollectionItemForm, WantedItemForm
from apps.collections.models import CollectionItem
from apps.core.models import LicenseType, State


class CollectionItemFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('keeper', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True})
        if cls.pa.min_license_year is None:
            cls.pa.min_license_year = 1913
            cls.pa.save(update_fields=['min_license_year'])
        cls.federal, _ = State.objects.get_or_create(
            code='FD', defaults={'name': 'Federal', 'slug': 'federal', 'min_license_year': 1934})
        cls.turkey = LicenseType.objects.create(
            state=cls.pa, name='Turkey Tag', category='addon_type', slug='c-pa-turkey-tag')
        cls.residency = LicenseType.objects.create(
            state=cls.pa, name='Resident', category='residency', slug='c-pa-resident')

    def _data(self, **overrides):
        data = {
            'item_kind': 'license', 'title': 'A license', 'state': str(self.pa.pk),
            'license_year': '1942', 'condition_grade': 'good', 'colors': ['red'],
            'resident_status': 'unknown',
        }
        data.update(overrides)
        return data

    def test_year_below_state_minimum_rejected(self):
        form = CollectionItemForm(data=self._data(license_year='1899'), user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('license_year', form.errors)
        self.assertIn('1913', ' '.join(form.errors['license_year']))

    def test_absolute_floor_guards_null_min_state(self):
        # Federal now has a 1934 floor; a sub-floor year is rejected, not saved.
        form = CollectionItemForm(data=self._data(state=str(self.federal.pk), license_year='850'),
                                  user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('license_year', form.errors)

    def test_year_widget_carries_state_bounds(self):
        form = CollectionItemForm(user=self.owner, initial={'state': self.pa.pk})
        attrs = form.fields['license_year'].widget.attrs
        self.assertEqual(attrs['min'], 1913)
        self.assertEqual(attrs['max'], timezone.now().year - 25)

    def test_addon_kind_clears_hidden_base_dimensions(self):
        form = CollectionItemForm(
            data=self._data(item_kind='addon', residency=str(self.residency.pk),
                            addon_type=[str(self.turkey.pk)]),
            instance=CollectionItem(owner=self.owner), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertFalse(item.license_types.filter(category='residency').exists())
        self.assertTrue(item.license_types.filter(name='Turkey Tag').exists())


class TheTradeToggleTests(TestCase):
    """The owner has to be able to turn it off, and the form has to offer it.

    Both templates rendered `form.trade_eligible` after the field became
    non-editable, which silently rendered nothing — so the one control the
    whole tradeability rule depends on was not on the page at all.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('toggler', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True})

    def _data(self, **overrides):
        data = {
            'item_kind': 'license', 'title': 'A license', 'state': str(self.pa.pk),
            'license_year': '1942', 'condition_grade': 'good', 'colors': ['red'],
            'resident_status': 'unknown',
        }
        data.update(overrides)
        return data

    def test_the_control_is_actually_on_the_page(self):
        # Turn 6 moved the standing answer to step 3 (the collection panel)
        # for a new piece; on an existing piece it stays on the edit page.
        self.client.force_login(self.owner)
        create = self.client.get(reverse('collections:create'))
        self.assertNotContains(create, 'name="tradeability"')

        item = CollectionItem.objects.create(owner=self.owner, title='On the shelf')
        terms = self.client.get(reverse('collections:item_terms', args=[item.pk]))
        self.assertContains(terms, 'name="open_to_trade"')
        self.assertContains(terms, 'name="trade_wants"')

        edit = self.client.get(reverse('collections:edit', args=[item.pk]))
        self.assertContains(edit, 'name="tradeability"')
        self.assertContains(edit, 'name="trade_wants"')

    def test_a_new_piece_is_open_without_being_told_to_be(self):
        form = CollectionItemForm(data=self._data(),
                                  instance=CollectionItem(owner=self.owner),
                                  user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().tradeability, 'open')

    def test_the_owner_can_close_one_and_say_what_they_want(self):
        form = CollectionItemForm(
            data=self._data(tradeability='closed', trade_wants='Anything pre-1930'),
            instance=CollectionItem(owner=self.owner), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual(item.tradeability, 'closed')
        self.assertEqual(item.trade_wants, 'Anything pre-1930')

    def test_a_form_without_the_block_leaves_a_closed_piece_closed(self):
        """A silence is 'unchanged', never 'open'."""
        item = CollectionItem.objects.create(
            owner=self.owner, title='Shut', state=self.pa,
            condition_grade='good', tradeability='closed')
        form = CollectionItemForm(data=self._data(title='Shut'),
                                  instance=item, user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().tradeability, 'closed')


class WantedItemFormTests(TestCase):
    """It reached for a `tradeability` field the wanted list does not have,
    so every wanted-item page raised KeyError before rendering."""

    def test_it_builds_without_reaching_for_a_field_it_does_not_have(self):
        State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'is_primary_default': True})
        form = WantedItemForm()
        self.assertIn('state', form.fields)
        self.assertNotIn('tradeability', form.fields)


class TwoStepStrikeTests(TestCase):
    """10.24 - nothing is deleted on one click, anywhere.

    The detail page keeps Edit only; the strike lives at the bottom of the
    edit form behind the shared confirm; the GET page is the no-JavaScript
    second step and deletes nothing by itself."""

    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'is_primary_default': True})
        cls.owner = User.objects.create_user('strike_owner', password='pw')
        cls.item = CollectionItem.objects.create(
            owner=cls.owner, title='1931 Cameron', state=cls.pa,
            condition_grade='good')

    def setUp(self):
        self.client.force_login(self.owner)

    def test_the_detail_page_keeps_edit_only(self):
        resp = self.client.get(
            reverse('collections:item_detail', args=[self.item.pk]))
        self.assertContains(resp, 'Edit the record')
        self.assertNotContains(resp, 'Strike it from the record')

    def test_my_collection_offers_no_bare_delete(self):
        resp = self.client.get(reverse('collections:my_collection'))
        self.assertNotContains(
            resp, reverse('collections:delete', args=[self.item.pk]))

    def test_the_edit_form_carries_the_trigger_and_the_plain_question(self):
        resp = self.client.get(reverse('collections:edit', args=[self.item.pk]))
        self.assertContains(resp, 'Strike it from the record')
        self.assertContains(resp, 'data-kb-confirm')
        self.assertContains(resp, 'It cannot be undone')

    def test_the_no_js_second_step_asks_first_and_deletes_on_post_only(self):
        url = reverse('collections:delete', args=[self.item.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Delete it permanently')
        self.assertContains(page, 'cannot be undone')
        self.assertTrue(CollectionItem.objects.filter(pk=self.item.pk).exists())

        resp = self.client.post(url)
        self.assertRedirects(resp, reverse('collections:my_collection'))
        self.assertFalse(CollectionItem.objects.filter(pk=self.item.pk).exists())

    def test_a_piece_on_its_way_to_market_cannot_be_struck(self):
        """Deleting the shelf half would orphan a live lot (10b)."""
        from decimal import Decimal

        from apps.listings.models import Listing

        Listing.objects.create(
            seller=self.owner, title='1931 Cameron lot', description='d',
            state=self.pa, condition_grade='good', listing_type='buy_now',
            buy_now_price=Decimal('25'), status='active',
            source_collection_item=self.item)
        resp = self.client.post(
            reverse('collections:delete', args=[self.item.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CollectionItem.objects.filter(pk=self.item.pk).exists())
