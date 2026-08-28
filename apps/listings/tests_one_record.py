"""One record, one editor — and the schedule unlocked (the field report).

A scheduled listing is not live: it edits on the step-2 page like a
draft, and its terms reopen freely — a new date reschedules, a cleared
date puts it up right now. And while any lot exists for a piece, the
collection editor redirects to the lot, with every lot save mirrored
back to the shelf record, so the pair can never tell two stories.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.listings.models import Listing
from apps.listings.tests_terms import TermsBase


class ScheduledUnlockedTests(TermsBase):
    def _scheduled(self):
        draft = self._draft('auction')
        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'starting_price': '40', 'duration_days': '7',
            # datetime-local speaks the wall clock, so format in local time.
            'scheduled_at': timezone.localtime(
                timezone.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M'),
        })
        draft.refresh_from_db()
        assert draft.status == 'scheduled', draft.status
        return draft

    def test_a_scheduled_listing_edits_on_the_step_two_page(self):
        listing = self._scheduled()
        resp = self.client.get(reverse('listings:item_edit', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        # And the old combined editor sends it there rather than serving
        # the pre-redesign form.
        resp = self.client.get(reverse('listings:edit', args=[listing.pk]))
        self.assertRedirects(resp, reverse('listings:item_edit', args=[listing.pk]))

    def test_the_terms_reopen_and_say_when_it_goes_up(self):
        listing = self._scheduled()
        resp = self.client.get(reverse('listings:terms', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Scheduled to go up')

    def test_a_new_date_reschedules(self):
        listing = self._scheduled()
        later = timezone.now() + timedelta(days=12)
        self.client.post(reverse('listings:terms', args=[listing.pk]), {
            'starting_price': '40', 'duration_days': '7',
            'scheduled_at': timezone.localtime(later).strftime('%Y-%m-%dT%H:%M'),
        })
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'scheduled')
        self.assertAlmostEqual(
            (listing.scheduled_at - later).total_seconds(), 0, delta=60)
        # The clock starts from the new go-live, not the old one.
        days = (listing.auction_end - later).total_seconds() / 86400
        self.assertAlmostEqual(days, 7, delta=0.1)

    def test_a_cleared_date_puts_it_up_now(self):
        listing = self._scheduled()
        self.client.post(reverse('listings:terms', args=[listing.pk]), {
            'starting_price': '40', 'duration_days': '7',
        })
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')
        self.assertIsNone(listing.scheduled_at)
        days = (listing.auction_end - timezone.now()).total_seconds() / 86400
        self.assertAlmostEqual(days, 7, delta=0.1)


class OneRecordTests(TermsBase):
    def test_the_collection_editor_redirects_to_the_operative_lot(self):
        draft = self._draft('auction')
        source = draft.source_collection_item
        self.assertIsNotNone(source)

        resp = self.client.get(reverse('collections:edit', args=[source.pk]))
        self.assertRedirects(resp, reverse('listings:item_edit', args=[draft.pk]))

        Listing.objects.filter(pk=draft.pk).update(status='active')
        resp = self.client.get(reverse('collections:edit', args=[source.pk]))
        self.assertRedirects(resp, reverse('listings:edit', args=[draft.pk]))

        # Once the lot is settled the shelf record is the editor again.
        Listing.objects.filter(pk=draft.pk).update(status='expired')
        resp = self.client.get(reverse('collections:edit', args=[source.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_a_lot_save_mirrors_back_to_the_shelf(self):
        draft = self._draft('auction')
        source = draft.source_collection_item

        self.client.post(reverse('listings:item_edit', args=[draft.pk]), {
            'listing_type': 'auction', 'item_kind': 'license',
            'title': 'A 1956 back tag, corrected',
            'description': 'Out of an estate lot.',
            'condition_grade': 'excellent', 'license_year': '1956',
            'state': str(self.pa.id),
            'additional_images-TOTAL_FORMS': '0',
            'additional_images-INITIAL_FORMS': '0',
            'additional_images-MIN_NUM_FORMS': '0',
            'additional_images-MAX_NUM_FORMS': '10',
        })
        source.refresh_from_db()
        self.assertEqual(source.title, 'A 1956 back tag, corrected')
        self.assertEqual(source.license_year, 1956)
        self.assertEqual(source.condition_grade, 'excellent')


class EditPhotosAreTheAddFormTests(TermsBase):
    """"Why not the add an item format we worked on" — no reason. Every
    editor now wears the same slot plan the add flow does, with the
    record's photographs already sitting in their slots."""

    def test_the_collection_editor_wears_the_slots(self):
        draft = self._draft('auction')
        source = draft.source_collection_item
        Listing.objects.filter(pk=draft.pk).update(status='expired')

        resp = self.client.get(reverse('collections:edit', args=[source.pk]))
        self.assertContains(resp, 'data-slots-ui')
        self.assertContains(resp, 'if-slot--front')
        self.assertNotContains(resp, 'travels with the file')
        self.assertNotContains(resp, 'Currently:')
        # And the dead trade-rules paragraph went with it — a piece with
        # a live lot cannot even reach this form since 10b.
        self.assertNotContains(resp, 'off the table until the lot closes')

    def test_the_live_editor_wears_the_slots_with_the_front_in_place(self):
        draft = self._draft('auction')
        Listing.objects.filter(pk=draft.pk).update(status='active')

        resp = self.client.get(reverse('listings:edit', args=[draft.pk]))
        self.assertContains(resp, 'data-slots-ui')
        # The saved front sits in its slot, marked as committed.
        self.assertContains(resp, 'data-existing="yes"')
        self.assertNotContains(resp, 'Currently:')
        self.assertNotContains(resp, 'travels with the file')


class TheMarketplaceIsAFactTests(TermsBase):
    """The live editor's quiet listing_type dropdown once turned a Store
    listing into a clockless auction that closed itself at $None. The
    marketplace is a fact on the live editor now; moving is a deliberate
    act that takes the listing off the market and back through the terms
    page, where the new marketplace's questions actually get asked."""

    def _live_store(self):
        draft = self._draft('buy_now')
        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'buy_now_price': '35.50', 'allow_offers': 'on',
        })
        draft.refresh_from_db()
        assert draft.status == 'active', draft.status
        return draft

    def _live_auction(self):
        draft = self._draft('auction')
        self.client.post(reverse('listings:terms', args=[draft.pk]), {
            'starting_price': '40', 'duration_days': '7',
        })
        draft.refresh_from_db()
        assert draft.status == 'active', draft.status
        return draft

    def test_the_type_cannot_be_flipped_by_a_post(self):
        listing = self._live_store()
        self.client.post(reverse('listings:edit', args=[listing.pk]), {
            'listing_type': 'auction',  # the old trap — now ignored
            'item_kind': 'license',
            'title': listing.title, 'description': 'Out of an estate lot.',
            'condition_grade': 'good', 'license_year': '1955',
            'state': str(self.pa.id),
            'buy_now_price': '35.50',
            'additional_images-TOTAL_FORMS': '0',
            'additional_images-INITIAL_FORMS': '0',
            'additional_images-MIN_NUM_FORMS': '0',
            'additional_images-MAX_NUM_FORMS': '10',
        })
        listing.refresh_from_db()
        self.assertEqual(listing.listing_type, 'buy_now')
        self.assertEqual(listing.status, 'active')
        self.assertIsNotNone(listing.buy_now_price)

    def test_the_editor_shows_a_fact_and_a_door(self):
        listing = self._live_store()
        resp = self.client.get(reverse('listings:edit', args=[listing.pk]))
        self.assertContains(resp, 'The General Store')
        self.assertContains(resp, 'Move to the Auction House')
        self.assertNotContains(resp, 'Started from')

    def test_moving_goes_off_market_then_through_the_terms(self):
        listing = self._live_store()
        resp = self.client.post(reverse('listings:move', args=[listing.pk]),
                                {'move_to': 'auction'})
        self.assertRedirects(resp, reverse('listings:terms', args=[listing.pk]))
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'draft')
        self.assertEqual(listing.listing_type, 'auction')

        # The terms page is the only thing that opens it again — with a
        # real clock and the store fields cleared properly.
        self.client.post(reverse('listings:terms', args=[listing.pk]), {
            'starting_price': '40', 'duration_days': '7',
        })
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')
        self.assertIsNotNone(listing.auction_end)
        self.assertIsNone(listing.buy_now_price)

    def test_a_lot_with_bids_stands(self):
        from apps.bids.models import Bid

        listing = self._live_auction()
        Bid.objects.create(listing=listing, bidder=self.buyer, amount=45)
        resp = self.client.post(reverse('listings:move', args=[listing.pk]),
                                {'move_to': 'buy_now'}, follow=True)
        self.assertContains(resp, 'bids stand')
        listing.refresh_from_db()
        self.assertEqual(listing.listing_type, 'auction')
        self.assertEqual(listing.status, 'active')

    def test_a_quiet_lot_can_move_to_the_store(self):
        listing = self._live_auction()
        self.client.post(reverse('listings:move', args=[listing.pk]),
                         {'move_to': 'buy_now'})
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'draft')
        self.assertEqual(listing.listing_type, 'buy_now')
        self.assertIsNone(listing.auction_end)

    def test_pending_offers_are_declined_with_a_letter(self):
        from apps.notifications.models import Notification
        from apps.offers.models import Offer
        from apps.offers.services import create_offer

        listing = self._live_store()
        offer, status = create_offer(
            listing=listing, from_user=self.buyer, amount=30)
        self.assertIsNotNone(offer, status)

        self.client.post(reverse('listings:move', args=[listing.pk]),
                         {'move_to': 'auction'})
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'declined')
        self.assertTrue(Notification.objects.filter(
            user=self.buyer, notification_type='offer_declined').exists())

    def test_a_wrecked_auction_never_prints_dollar_none(self):
        listing = self._live_auction()
        Listing.objects.filter(pk=listing.pk).update(
            status='expired', current_bid=None, starting_price=None)
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertNotContains(resp, '$None')
        self.assertNotContains(resp, '>None<')
