"""The collection add/edit form — the same 6b column as the listing form,
so the three destinations share one step 2."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import CollectionItem
from apps.core.models import State


class CollectionFormBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('cf_owner', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def _item(self, **kwargs):
        defaults = dict(
            owner=self.owner, title='1949 Tioga', description='d',
            state=self.pa, license_year=1949, condition_grade='good',
        )
        defaults.update(kwargs)
        return CollectionItem.objects.create(**defaults)


class TheAddItemDrawingTests(CollectionFormBase):
    def test_title_and_description_lead_like_the_listing_form(self):
        # Turn 6b: plain names, first thing on the page, side by side —
        # the Turn-5 "What it's called" panel and its escape hatch are gone.
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'data-title-note')
        self.assertNotContains(resp, 'What it&rsquo;s called')
        self.assertNotContains(resp, 'Write my own')

    def test_the_taxonomy_is_out_of_the_drawer_here_too(self):
        # "Taxonomy, out of the drawer" (6b) applies to every destination's
        # step 2 — the collections form kept a <details> drawer for a pass
        # too long.
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'The detail collectors filter on')
        self.assertNotContains(resp, 'The finer detail')

    def test_a_record_can_be_as_thin_as_the_collector_likes(self):
        # No at-least-one-attribute rule on a shelf record — that rule
        # gates *publishing*, and this is the collector's own catalogue.
        resp = self.client.post(reverse('collections:create'), {
            'item_kind': 'license', 'title': 'A thin record',
            'state': str(self.pa.id),
            'images-TOTAL_FORMS': '0', 'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0', 'images-MAX_NUM_FORMS': '12',
        })
        item = CollectionItem.objects.get(title='A thin record')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(item.license_types.count(), 0)

    def test_five_photograph_slots(self):
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'data-slot="detail2"')
        self.assertContains(
            resp, 'name="images-TOTAL_FORMS" value="5"')

    def test_the_private_block_moved_to_the_collection_panel(self):
        # Turn 6: step 2 describes the item; the only-you block is a step-3
        # question. It stays inline on the edit page.
        create = self.client.get(reverse('collections:create'))
        self.assertNotContains(create, 'name="purchase_price"')

        item = self._item()
        terms = self.client.get(reverse('collections:item_terms', args=[item.pk]))
        self.assertContains(terms, 'Only you ever see this')
        self.assertContains(terms, 'What you paid')
        self.assertContains(terms, 'name="purchase_price"')

        edit = self.client.get(reverse('collections:edit', args=[item.pk]))
        self.assertContains(edit, 'Only you see these')
        self.assertContains(edit, 'name="purchase_price"')

    def test_a_new_piece_is_not_asked_where_it_is(self):
        """Disposition is an edit-time fact — a piece being added is in hand."""
        resp = self.client.get(reverse('collections:create'))
        self.assertNotContains(resp, 'name="disposition"')

    def test_an_edit_can_record_a_departure(self):
        item = self._item()
        resp = self.client.get(reverse('collections:edit', args=[item.pk]))
        self.assertContains(resp, 'Where it is')
        self.assertContains(resp, 'name="disposition"')
        self.assertContains(resp, 'Sold elsewhere')
        # ...but never offers to fake a trade.
        self.assertNotContains(resp, 'Traded away here')


class TheDetailSheetTests(CollectionFormBase):
    def test_a_departed_piece_says_where_it_went_instead_of_open(self):
        item = self._item(disposition='sold_elsewhere')
        resp = self.client.get(reverse('collections:item_detail', args=[item.pk]))
        self.assertContains(resp, 'Sold elsewhere')
        self.assertNotContains(resp, 'Open to trade')
        # And the owner is not offered a sale on a piece that left.
        self.assertNotContains(resp, 'Sell it')

    def test_the_private_block_shows_only_to_the_owner(self):
        item = self._item(purchase_price='48.00', acquired_note='Mar 2026, Bloomsburg')
        resp = self.client.get(reverse('collections:item_detail', args=[item.pk]))
        self.assertContains(resp, 'Only you see this')
        self.assertContains(resp, 'Mar 2026, Bloomsburg')

        visitor = User.objects.create_user('cf_visitor', password='pw')
        self.client.force_login(visitor)
        resp = self.client.get(reverse('collections:item_detail', args=[item.pk]))
        self.assertNotContains(resp, 'Only you see this')
        self.assertNotContains(resp, 'Mar 2026, Bloomsburg')

    def test_thumbnails_say_what_each_photograph_is(self):
        item = self._item()
        resp = self.client.get(reverse('collections:item_detail', args=[item.pk]))
        self.assertEqual(resp.status_code, 200)
        # No photographs: the plate says so rather than drawing nothing.
        self.assertContains(resp, 'No photograph yet')
