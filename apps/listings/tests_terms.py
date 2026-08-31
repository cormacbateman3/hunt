"""Step 3 — the terms page, and the draft that leads to it.

Turn 6c's contract: step 2 saves a draft and never publishes; the terms
page carries one destination's questions plus the shared getting-it-there
strip; its foot button is the only thing on the site that makes a listing
public. A draft has no public face at all.
"""

import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.collections.models import CollectionItem, WantedItem
from apps.core.models import LicenseType, State
from apps.listings.models import Listing


def _png(name='front.png'):
    import struct
    import zlib

    def chunk(tag, data):
        payload = tag + data
        return (struct.pack('>I', len(data)) + payload
                + struct.pack('>I', zlib.crc32(payload) & 0xffffffff))

    raw = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
           + chunk(b'IEND', b''))
    return SimpleUploadedFile(name, raw, content_type='image/png')


class TermsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('terms_seller', password='pw')
        cls.buyer = User.objects.create_user('terms_buyer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913, 'is_primary_default': True},
        )
        cls.residency, _ = LicenseType.objects.get_or_create(
            name='Resident', category='residency',
            defaults={'slug': 'terms-resident'},
        )
        address = Address.objects.create(
            user=cls.seller, full_name='Seller', line1='1 Main St',
            city='Williamsport', state='PA', postal_code='17701')
        profile = cls.seller.profile
        profile.email_verified = True
        profile.shipping_address = address
        profile.save(update_fields=['email_verified', 'shipping_address'])

    def setUp(self):
        self.client.force_login(self.seller)

    def _step2(self, to='auction', **overrides):
        data = {
            'listing_type': to, 'item_kind': 'license',
            'title': 'A 1955 back tag', 'description': 'Out of an estate lot.',
            'condition_grade': 'good', 'license_year': '1955',
            'state': str(self.pa.id), 'residency': str(self.residency.id),
            'featured_image': _png(),
            'additional_images-TOTAL_FORMS': '0',
            'additional_images-INITIAL_FORMS': '0',
            'additional_images-MIN_NUM_FORMS': '0',
            'additional_images-MAX_NUM_FORMS': '10',
        }
        data.update(overrides)
        return self.client.post(reverse('listings:create'), data)

    def _draft(self, to='auction'):
        self._step2(to)
        return Listing.objects.latest('created_at')


class TheDraftTests(TermsBase):
    def test_step_two_saves_a_draft_and_walks_to_the_terms(self):
        resp = self._step2('auction')
        listing = Listing.objects.get(title='A 1955 back tag')
        self.assertEqual(listing.status, 'draft')
        self.assertIsNone(listing.auction_end)
        self.assertRedirects(resp, reverse('listings:terms', args=[listing.pk]))

    def test_save_and_come_back_lands_on_my_listings(self):
        resp = self._step2('buy_now', save_draft='1')
        listing = Listing.objects.latest('created_at')
        self.assertEqual(listing.status, 'draft')
        self.assertRedirects(resp, reverse('listings:my_listings'))

    def test_the_shelf_item_behind_a_draft_is_born_quiet(self):
        draft = self._draft()
        self.assertIsNotNone(draft.source_collection_item)
        self.assertFalse(draft.source_collection_item.is_public)

    def test_a_draft_has_no_public_face(self):
        draft = self._draft()
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('listings:detail', args=[draft.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_the_seller_is_walked_from_detail_to_the_terms(self):
        draft = self._draft()
        resp = self.client.get(reverse('listings:detail', args=[draft.pk]))
        self.assertRedirects(resp, reverse('listings:terms', args=[draft.pk]))


class TheBrowserShapedPostTests(TermsBase):
    """The slot JS posts image_role and sort_order for EVERY formset row,
    files or not. Those rows must read as empty slots — they once read as
    rows missing their required image: four errors rendered only inside
    hidden inputs, and a submit that looked dead."""

    def test_the_exact_post_a_browser_sends_saves(self):
        resp = self._step2('auction', **{
            'additional_images-TOTAL_FORMS': '4',
            'additional_images-MAX_NUM_FORMS': '4',
            'additional_images-0-image_role': 'back',
            'additional_images-0-sort_order': '0',
            'additional_images-1-image_role': 'detail',
            'additional_images-1-sort_order': '1',
            'additional_images-2-image_role': 'detail',
            'additional_images-2-sort_order': '2',
            'additional_images-3-image_role': 'detail',
            'additional_images-3-sort_order': '3',
        })
        listing = Listing.objects.get(title='A 1955 back tag')
        self.assertEqual(listing.status, 'draft')
        self.assertRedirects(resp, reverse('listings:terms', args=[listing.pk]))

    def test_a_photograph_error_is_never_invisible(self):
        """A genuinely bad row (corrupt file) must surface in the band —
        per-row errors used to render only inside the hidden inputs."""
        resp = self._step2('auction', **{
            'additional_images-TOTAL_FORMS': '4',
            'additional_images-MAX_NUM_FORMS': '4',
            'additional_images-0-image': SimpleUploadedFile(
                'back.png', b'not really a png', content_type='image/png'),
            'additional_images-0-image_role': 'back',
            'additional_images-0-sort_order': '0',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Something to fix')
        self.assertContains(resp, 'Photograph 1')


class TheThinDraftTests(TermsBase):
    """Step 2 never hard-blocks. Required-to-publish fields gate publishing
    — at the terms page — so a draft can be as thin as a title, and the
    foot buttons always do something visible."""

    def _thin(self, **overrides):
        data = {
            'listing_type': 'auction', 'item_kind': 'license',
            'title': 'Just a title so far',
            'additional_images-TOTAL_FORMS': '0',
            'additional_images-INITIAL_FORMS': '0',
            'additional_images-MIN_NUM_FORMS': '0',
            'additional_images-MAX_NUM_FORMS': '10',
        }
        data.update(overrides)
        return self.client.post(reverse('listings:create'), data)

    def test_a_draft_can_be_as_thin_as_a_title(self):
        resp = self._thin()
        listing = Listing.objects.get(title='Just a title so far')
        self.assertEqual(listing.status, 'draft')
        self.assertRedirects(resp, reverse('listings:terms', args=[listing.pk]))

    def test_the_terms_page_names_what_is_missing(self):
        self._thin()
        listing = Listing.objects.get(title='Just a title so far')
        resp = self.client.get(reverse('listings:terms', args=[listing.pk]))
        self.assertContains(resp, 'Before it can go up, the item still needs:')
        self.assertContains(resp, 'a front photograph')
        self.assertContains(resp, 'a condition grade')
        self.assertContains(resp, 'Finish the item')

    def test_a_thin_draft_cannot_be_published(self):
        self._thin()
        listing = Listing.objects.get(title='Just a title so far')
        self.client.post(reverse('listings:terms', args=[listing.pk]), {
            'starting_price': '40', 'duration_days': '7',
        })
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'draft')
        self.assertIsNone(listing.auction_end)

    def test_a_complete_draft_shows_no_gaps(self):
        self._step2('auction')
        listing = Listing.objects.latest('created_at')
        resp = self.client.get(reverse('listings:terms', args=[listing.pk]))
        self.assertNotContains(resp, 'Before it can go up')


class TheItemEditTests(TermsBase):
    """Step 2, revisited — a draft's item fields edit on the step-2 page,
    photographs in their slots, and the road still leads to the terms."""

    def test_the_page_wears_the_step_two_clothes(self):
        draft = self._draft('auction')
        resp = self.client.get(reverse('listings:item_edit', args=[draft.pk]))
        self.assertContains(resp, 'Set the terms')
        self.assertContains(resp, 'Save and come back to it')
        self.assertContains(resp, 'A 1955 back tag')
        # The saved front photograph hangs in its slot.
        self.assertContains(resp, 'data-existing="yes"')

    def test_a_live_listing_is_sent_to_the_real_edit_page(self):
        draft = self._draft('auction')
        Listing.objects.filter(pk=draft.pk).update(status='active')
        resp = self.client.get(reverse('listings:item_edit', args=[draft.pk]))
        self.assertRedirects(resp, reverse('listings:edit', args=[draft.pk]))

    def test_somebody_else_cannot_edit_your_draft(self):
        draft = self._draft('auction')
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('listings:item_edit', args=[draft.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_saving_walks_back_to_the_terms(self):
        draft = self._draft('buy_now')
        resp = self.client.post(reverse('listings:item_edit', args=[draft.pk]), {
            'listing_type': 'buy_now', 'item_kind': 'license',
            'title': 'A 1955 back tag, retitled',
            'description': 'Out of an estate lot.',
            'condition_grade': 'good', 'license_year': '1955',
            'state': str(self.pa.id), 'residency': str(self.residency.id),
            'additional_images-TOTAL_FORMS': '0',
            'additional_images-INITIAL_FORMS': '0',
            'additional_images-MIN_NUM_FORMS': '0',
            'additional_images-MAX_NUM_FORMS': '10',
        })
        self.assertRedirects(resp, reverse('listings:terms', args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.title, 'A 1955 back tag, retitled')
        self.assertEqual(draft.status, 'draft')


class TheKeptUploadTests(TermsBase):
    """A photograph survives a failed submit *in its slot* — no notice box,
    no re-picking, and no stash haunting the next fresh walk-up."""

    def test_the_kept_photograph_hangs_back_in_its_slot(self):
        resp = self._step2('auction', title='')   # fails: title required
        self.assertContains(resp, 'data-kept="featured_image"')
        self.assertNotContains(resp, 'kept through the error')

    def test_the_retry_does_not_need_the_file_again(self):
        self._step2('auction', title='')
        resp = self._step2('auction', title='Second try', featured_image='')
        listing = Listing.objects.get(title='Second try')
        self.assertTrue(listing.featured_image)
        self.assertRedirects(resp, reverse('listings:terms', args=[listing.pk]))

    def test_clicking_the_slots_x_really_lets_go(self):
        self._step2('auction', title='')
        resp = self._step2('auction', title='No photo after all',
                           featured_image='', discard_kept='featured_image')
        listing = Listing.objects.get(title='No photo after all')
        self.assertFalse(listing.featured_image)

    def test_a_fresh_walk_up_starts_clean(self):
        self._step2('auction', title='')   # stash now holds the upload
        resp = self.client.get(reverse('listings:create') + '?to=auction')
        self.assertNotContains(resp, 'data-kept')


class TheTermsPageTests(TermsBase):
    def test_the_auction_panel_carries_its_own_questions(self):
        draft = self._draft('auction')
        resp = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertContains(resp, 'The Auction House')
        self.assertContains(resp, 'Starting price')
        self.assertContains(resp, 'Reserve')
        self.assertContains(resp, 'Runs for')
        self.assertContains(resp, 'Smallest raise')
        self.assertContains(resp, 'Relist it if it doesn&rsquo;t sell')
        self.assertContains(resp, 'Open the lot')
        self.assertContains(resp, 'You can cancel a lot until the first bid is in.')
        self.assertContains(resp, 'Getting it there')
        self.assertNotContains(resp, 'Your price')

    def test_the_store_panel_carries_its_own_questions(self):
        draft = self._draft('buy_now')
        resp = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertContains(resp, 'The General Store')
        self.assertContains(resp, 'Your price')
        self.assertContains(resp, 'You&rsquo;d keep')
        self.assertContains(resp, 'I&rsquo;ll consider offers')
        self.assertContains(resp, 'Open to trade offers too')
        self.assertContains(resp, 'Put it in the Store')
        self.assertNotContains(resp, 'Starting price')

    def test_the_terms_of_a_live_listing_live_on_the_edit_page(self):
        draft = self._draft('auction')
        Listing.objects.filter(pk=draft.pk).update(status='active')
        resp = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertRedirects(resp, reverse('listings:edit', args=[draft.pk]))

    def test_somebody_else_cannot_see_your_terms(self):
        draft = self._draft('auction')
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_the_books_count_the_collectors_who_want_this_ground(self):
        draft = self._draft('buy_now')
        WantedItem.objects.create(user=self.buyer, state=self.pa,
                                  year_min=1950, year_max=1960)
        resp = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertContains(resp, 'What the books say')
        self.assertContains(resp, 'One collector has')


class ThePublishTests(TermsBase):
    def test_opening_the_lot_starts_the_clock(self):
        draft = self._draft('auction')
        resp = self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'starting_price': '40', 'reserve_price': '240',
            'duration_days': '7', 'bid_increment': '5',
        })
        draft.refresh_from_db()
        self.assertRedirects(resp, reverse('listings:detail', args=[draft.pk]))
        self.assertEqual(draft.status, 'active')
        self.assertIsNotNone(draft.auction_end)
        days = (draft.auction_end - timezone.now()).total_seconds() / 86400
        self.assertAlmostEqual(days, 7, delta=0.1)
        # The piece steps into the light with its lot.
        self.assertTrue(draft.source_collection_item.is_public)

    def test_a_later_start_schedules_instead(self):
        draft = self._draft('auction')
        go_live = timezone.localtime(timezone.now() + timezone.timedelta(days=3))
        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'starting_price': '40', 'duration_days': '7',
            'scheduled_at': go_live.strftime('%Y-%m-%dT%H:%M'),
        })
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'scheduled')

    def test_the_store_needs_a_price_before_it_goes_up(self):
        draft = self._draft('buy_now')
        resp = self.client.post(reverse('listings:terms', args=[draft.pk]), {})
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'draft')
        self.assertContains(resp, 'Your price is required')

    def test_the_trade_switch_writes_the_standing_answer_on_the_piece(self):
        draft = self._draft('buy_now')
        source = draft.source_collection_item
        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'buy_now_price': '285',
            'open_to_trade': 'on',
            'trade_wants': 'Anything pre-1930 from a county I am missing.',
        })
        source.refresh_from_db()
        self.assertEqual(source.tradeability, 'open')
        self.assertIn('pre-1930', source.trade_wants)

        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'buy_now_price': '285',
        })
        draft.refresh_from_db()
        source.refresh_from_db()
        # Published on the first post; the second lands on the edit page
        # instead of silently republishing.
        self.assertEqual(draft.status, 'active')
        self.assertEqual(source.tradeability, 'open')


class TheWaysOutTests(TermsBase):
    """6a: "You can move an item between all three later" — and a draft can
    move now. Plus the door out: a discard parks the work on the shelf."""

    def test_a_draft_can_change_marketplaces_without_losing_the_item(self):
        draft = self._draft('auction')
        resp = self.client.post(reverse('listings:terms', args=[draft.pk]),
                                {'switch_to': 'buy_now'})
        self.assertRedirects(resp, reverse('listings:terms', args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.listing_type, 'buy_now')
        self.assertEqual(draft.status, 'draft')
        page = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertContains(page, 'Put it in the Store')

    def test_keeping_it_walks_to_the_collection_panel(self):
        draft = self._draft('buy_now')
        source = draft.source_collection_item
        resp = self.client.post(reverse('listings:terms', args=[draft.pk]),
                                {'to_collection': '1'})
        self.assertRedirects(resp, reverse('collections:item_terms', args=[source.pk]))
        self.assertFalse(Listing.objects.filter(pk=draft.pk).exists())
        source.refresh_from_db()   # still on the shelf

    def test_a_discard_parks_the_item_on_the_shelf(self):
        draft = self._draft('auction')
        source = draft.source_collection_item
        resp = self.client.post(reverse('listings:terms', args=[draft.pk]),
                                {'discard': '1'})
        self.assertRedirects(resp, reverse('listings:sell_start'))
        self.assertFalse(Listing.objects.filter(pk=draft.pk).exists())
        self.assertTrue(CollectionItem.objects.filter(pk=source.pk).exists())

    def test_the_rail_walks_both_ways(self):
        draft = self._draft('auction')
        terms = self.client.get(reverse('listings:terms', args=[draft.pk]))
        self.assertContains(terms, reverse('listings:item_edit', args=[draft.pk]))
        self.assertContains(terms, reverse('listings:sell_start'))
        item_page = self.client.get(reverse('listings:item_edit', args=[draft.pk]))
        self.assertContains(item_page, reverse('listings:terms', args=[draft.pk]))


class TheShelfSkipTests(TermsBase):
    """Selling from the shelf: the door-picker writes the draft from the
    item and lands on step 2 with everything filled in — a look-over on
    the way to the terms, not a retype."""

    def _item(self, **overrides):
        fields = dict(owner=self.seller, title='A 1955 duplicate',
                      state=self.pa, license_year=1955, condition_grade='good')
        fields.update(overrides)
        item = CollectionItem.objects.create(**fields)
        item.license_types.add(self.residency)
        return item

    def test_the_review_shows_the_item_and_the_two_selling_doors(self):
        item = self._item()
        resp = self.client.get(reverse('listings:sell_from', args=[item.pk]))
        self.assertContains(resp, 'A 1955 duplicate')
        self.assertContains(resp, 'look the details over')
        self.assertContains(resp, 'The Auction House')
        self.assertContains(resp, 'The General Store')
        self.assertNotContains(resp, 'My collection</span>')

    def test_choosing_a_door_writes_the_draft_and_lands_on_step_two(self):
        item = self._item()
        resp = self.client.get(
            reverse('listings:sell_from', args=[item.pk]) + '?to=auction')
        draft = Listing.objects.get(source_collection_item=item)
        self.assertRedirects(resp, reverse('listings:item_edit', args=[draft.pk]))
        self.assertEqual(draft.status, 'draft')
        self.assertEqual(draft.listing_type, 'auction')
        self.assertEqual(draft.title, item.title)
        self.assertEqual(draft.county_ref, item.county)
        self.assertTrue(draft.license_types.filter(pk=self.residency.pk).exists())

    def test_the_landing_page_shows_the_carried_details(self):
        item = self._item()
        self.client.get(reverse('listings:sell_from', args=[item.pk]) + '?to=auction')
        draft = Listing.objects.get(source_collection_item=item)
        resp = self.client.get(reverse('listings:item_edit', args=[draft.pk]))
        self.assertContains(resp, 'A 1955 duplicate')
        self.assertContains(resp, 'Set the terms')

    def test_coming_back_resumes_the_draft_rather_than_multiplying_it(self):
        item = self._item()
        url = reverse('listings:sell_from', args=[item.pk]) + '?to=buy_now'
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(Listing.objects.filter(source_collection_item=item).count(), 1)

    def test_an_item_already_live_is_turned_back(self):
        item = self._item()
        Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='Live', description='d',
            condition_grade='good', status='active', source_collection_item=item)
        resp = self.client.get(reverse('listings:sell_from', args=[item.pk]))
        self.assertRedirects(resp, reverse('listings:sell_start'))

    def test_somebody_else_cannot_sell_your_shelf(self):
        item = self._item()
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('listings:sell_from', args=[item.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_the_old_query_string_walks_into_the_skip(self):
        item = self._item()
        resp = self.client.get(
            reverse('listings:create') + f'?from_item={item.pk}&to=buy_now')
        self.assertRedirects(
            resp,
            reverse('listings:sell_from', args=[item.pk]) + '?to=buy_now',
            target_status_code=302,
        )


class TwoStepDiscardTests(TermsBase):
    """10.24 - deleting a draft takes a second, plainly-worded click."""

    def test_the_discard_button_asks_before_it_acts(self):
        listing = self._draft('buy_now')
        html = self.client.get(
            reverse('listings:terms', args=[listing.pk])).content.decode()
        self.assertIn('Discard this draft', html)
        self.assertIn('data-kb-confirm', html)
        self.assertIn('It cannot be undone', html)

    def test_every_draft_has_a_shelf_twin_so_the_page_may_promise_one(self):
        """The confirm says the piece stays on the shelf. That is only
        allowed to be unconditional because step 2 gives every draft a
        shelf twin (4e) - this locks the invariant the copy leans on."""
        listing = self._draft('buy_now')
        self.assertIsNotNone(listing.source_collection_item)
        html = self.client.get(
            reverse('listings:terms', args=[listing.pk])).content.decode()
        self.assertIn('Keep it in my collection', html)
        self.assertIn('stays on your collection shelf', html)
