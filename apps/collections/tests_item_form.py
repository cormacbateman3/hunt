"""The collection add/edit form against the turn 5b frame."""

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
    def test_the_written_for_you_title_panel_with_its_escape(self):
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'What it&rsquo;s called')
        self.assertContains(resp, 'Written from your answers')
        self.assertContains(resp, 'Write my own')

    def test_the_finer_detail_stays_in_one_drawer_here(self):
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'The finer detail')
        self.assertContains(resp, 'mostly filled from your photograph already')

    def test_five_photograph_slots(self):
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'data-slot="detail2"')
        self.assertContains(
            resp, 'name="images-TOTAL_FORMS" value="5"')

    def test_the_private_block_is_finally_on_the_form(self):
        resp = self.client.get(reverse('collections:create'))
        self.assertContains(resp, 'Only you see these')
        self.assertContains(resp, 'What you paid')
        self.assertContains(resp, 'name="purchase_price"')

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
