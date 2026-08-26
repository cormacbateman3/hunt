"""The letters, against turn 9a.

The design's charge against the old email was specific: *"a generic wrapper
that prints an enum label as a heading and pastes notification.message under
it. Nobody who receives one knows what to do without opening the site and
going looking."* These tests hold the letters to the opposite — the item,
the number and the clock in the first line, one action, and a footer that
says why it arrived.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.bids.models import Bid
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing
from apps.notifications import letters
from apps.notifications.models import Notification
from apps.notifications.services import send_notification_email
from apps.orders.models import AddressSnapshot, Order


class LetterBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            'lt_seller', email='seller@example.com', password='pw')
        profile = cls.seller.profile
        profile.display_name = 'Harold Kreider'
        profile.save()
        cls.buyer = User.objects.create_user(
            'lt_buyer', email='buyer@example.com', password='pw')
        buyer_profile = cls.buyer.profile
        buyer_profile.display_name = 'Ray Musser'
        buyer_profile.save()

        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )
        # A real county has a FIPS shape — the gap sentence now refuses
        # county-type rows without one (administrative codes, not ground).
        cls.sullivan = GeographicUnit.objects.create(
            state=cls.pa, name='Sullivan', unit_type='County',
            fips_code='42113', slug='pa-sullivan-letters')
        cls.listing = Listing.objects.create(
            seller=cls.seller, title='1921 Sullivan resident button',
            description='d', state=cls.pa, county_ref=cls.sullivan,
            license_year=1921, condition_grade='very_good',
            listing_type='auction', starting_price=Decimal('380.00'),
            current_bid=Decimal('402.00'), bid_increment=Decimal('10.00'),
            auction_end=timezone.now() + timedelta(hours=4), status='active',
        )

    def _note(self, kind, link_url, user=None, message='Something happened.'):
        return Notification.objects.create(
            user=user or self.buyer, notification_type=kind,
            message=message, link_url=link_url)

    def _order(self, **kwargs):
        snapshot = AddressSnapshot.objects.create(
            full_name='Ray Musser', line1='2 Pine St', city='Williamsport',
            state='PA', postal_code='17701')
        defaults = dict(
            buyer=self.buyer, seller=self.seller, listing=self.listing,
            order_type='auction', status='paid',
            item_amount=Decimal('212.00'), shipping_amount=Decimal('8.40'),
            platform_fee_amount=Decimal('16.00'),
            total_amount=Decimal('220.40'), ship_to_snapshot=snapshot,
        )
        defaults.update(kwargs)
        return Order.objects.create(**defaults)


class SayingThingsAloudTests(LetterBase):
    def test_money_dates_and_clocks_read_as_words(self):
        self.assertEqual(letters.money(Decimal('220.4')), '$220.40')
        self.assertEqual(letters.money(Decimal('1234.5')), '$1,234.50')
        when = timezone.now() + timedelta(hours=4)
        self.assertEqual(letters.remaining(when), 'about four hours')
        self.assertEqual(
            letters.remaining(timezone.now() + timedelta(minutes=20)),
            'under an hour')
        self.assertEqual(
            letters.remaining(timezone.now() + timedelta(days=2)),
            'about two days')

    def test_the_day_is_built_without_a_platform_specific_format(self):
        """%-d is not portable to Windows and has broken this repo before."""
        stamp = timezone.make_aware(timezone.datetime(2026, 8, 6, 9, 0))
        self.assertEqual(letters.day(stamp), 'Thursday 6 August')

    def test_emphasis_bolds_ours_and_escapes_theirs(self):
        out = str(letters.emphasis('Settle within **24 hours** now'))
        self.assertIn('<strong', out)
        self.assertIn('24 hours', out)
        hostile = str(letters.emphasis('<script>alert(1)</script>'))
        self.assertNotIn('<script>', hostile)
        self.assertIn('&lt;script&gt;', hostile)


class TheOutbidLetterTests(LetterBase):
    def setUp(self):
        Bid.objects.create(
            listing=self.listing, bidder=self.buyer, amount=Decimal('390.00'))

    def test_it_carries_the_item_the_numbers_and_the_clock(self):
        letter = letters.build(self._note('outbid', f'/listings/{self.listing.pk}/'))
        self.assertEqual(
            letter['headline'],
            'Somebody has gone past you on the 1921 Sullivan resident button.')
        facts = ' '.join(letter['item']['facts'])
        self.assertIn('Your bid was $390.00. It is now at $402.00.', facts)
        # "today" only when the close does not cross midnight, which four
        # hours from now may well do — the clock and the countdown always come.
        self.assertIn('Closes', facts)
        self.assertIn('about four hours', facts)

    def test_the_action_is_the_next_bid_not_a_dashboard_link(self):
        letter = letters.build(self._note('outbid', f'/listings/{self.listing.pk}/'))
        self.assertEqual(letter['action']['label'], 'Bid $412.00 and stay in it')
        self.assertEqual(letter['action']['tone'], 'dark')

    def test_a_county_you_lack_is_named_and_one_you_hold_is_not(self):
        from apps.collections.models import CollectionItem

        letter = letters.build(self._note('outbid', f'/listings/{self.listing.pk}/'))
        self.assertIn('That would be your first Sullivan.', letter['closing'])

        CollectionItem.objects.create(
            owner=self.buyer, title='1921 Sullivan', description='',
            state=self.pa, county=self.sullivan, license_year=1921,
            condition_grade='good')
        letter = letters.build(self._note('outbid', f'/listings/{self.listing.pk}/'))
        self.assertNotIn('your first Sullivan', letter['closing'])

    def test_the_plain_part_puts_the_apostrophes_back(self):
        """The closing is escaped on its way to HTML; text must not show it."""
        letter = letters.build(self._note('outbid', f'/listings/{self.listing.pk}/'))
        text = letters.as_text(letter)
        self.assertIn("If you'd rather let this one go", text)
        self.assertNotIn('&#x27;', text)
        self.assertNotIn('&amp;', text)

    def test_it_is_opt_out_able_because_it_is_not_a_deal_in_progress(self):
        letter = letters.build(self._note('outbid', f'/listings/{self.listing.pk}/'))
        self.assertTrue(letter['can_opt_out'])
        self.assertEqual(letter['reason'], 'You get this because you bid on it.')


class TheWonLetterTests(LetterBase):
    def test_it_names_them_the_price_and_the_total_with_shipping(self):
        order = self._order()
        letter = letters.build(
            self._note('auction_won', f'/orders/{order.pk}/'))
        self.assertEqual(
            letter['headline'], 'The 1921 Sullivan resident button is yours, Ray.')
        facts = ' '.join(letter['item']['facts'])
        self.assertIn('Won at $212.00 from Harold Kreider', facts)
        self.assertIn('With shipping to Williamsport: $220.40', facts)

    def test_one_bid_is_a_bid_not_bids(self):
        Bid.objects.create(
            listing=self.listing, bidder=self.buyer, amount=Decimal('212.00'))
        order = self._order()
        letter = letters.build(self._note('auction_won', f'/orders/{order.pk}/'))
        facts = ' '.join(letter['item']['facts'])
        self.assertIn('after one bid.', facts)
        self.assertNotIn('one bids', facts)

    def test_the_button_carries_the_figure_and_the_clock_has_a_consequence(self):
        order = self._order()
        letter = letters.build(self._note('auction_won', f'/orders/{order.pk}/'))
        self.assertEqual(letter['action']['label'], 'Pay $220.40')
        self.assertEqual(letter['action']['tone'], 'brass')
        self.assertIn('<strong', letter['closing'])
        self.assertIn('24 hours', letter['closing'])
        self.assertIn('nobody wants over a forgotten evening', letter['closing'])

    def test_a_deal_in_progress_says_it_always_comes(self):
        order = self._order()
        letter = letters.build(self._note('auction_won', f'/orders/{order.pk}/'))
        self.assertFalse(letter['can_opt_out'])
        self.assertEqual(letter['reason'],
                         'Letters about a deal in progress always come.')
        self.assertEqual(letter['sign_off'],
                         'Trouble paying? Reply and a person will answer.')


class TheShipByLetterTests(LetterBase):
    def test_it_says_who_paid_when_and_what_the_date_is(self):
        order = self._order(status='paid')
        letter = letters.build(
            self._note('order_ship_reminder', f'/orders/{order.pk}/',
                       user=self.seller))
        self.assertIn('wants posting', letter['headline'])
        self.assertIn('Ray Musser paid on', letter['lead'])
        self.assertIn('Five days puts your date at', letter['lead'])

    def test_the_three_ways_out_are_offered(self):
        order = self._order(status='paid')
        letter = letters.build(
            self._note('order_ship_reminder', f'/orders/{order.pk}/',
                       user=self.seller))
        leads = [lead for lead, _rest in letter['options']]
        self.assertEqual(leads, [
            'Buying the label here',
            'Using your own postage',
            'Meeting in person, or agreed a later date?',
        ])
        # Never "him" — the letter does not know anybody's pronouns.
        rest = ' '.join(rest for _lead, rest in letter['options'])
        self.assertIn('Offer them a handshake', rest)


class TheRestOfTheShellTests(LetterBase):
    def test_the_sold_letter_leads_with_the_figure(self):
        order = self._order()
        letter = letters.build(
            self._note('auction_sold', f'/orders/{order.pk}/', user=self.seller))
        self.assertIn('sold for $212.00', letter['headline'])
        self.assertIn('Ray Musser won it.', ' '.join(letter['item']['facts']))

    def test_the_unsold_letter_says_nothing_is_owed(self):
        letter = letters.build(
            self._note('auction_expired', f'/listings/{self.listing.pk}/',
                       user=self.seller))
        self.assertIn('ended without a winner', letter['headline'])
        self.assertIn('nothing was sold and nothing is owed', letter['closing'])
        self.assertEqual(letter['action']['label'], 'Put it up again')

    def test_the_payment_letter_names_the_seller_deadline(self):
        order = self._order()
        letter = letters.build(
            self._note('payment_confirmed', f'/orders/{order.pk}/'))
        facts = ' '.join(letter['item']['facts'])
        self.assertIn('$220.40 paid to Harold Kreider.', facts)
        self.assertIn('They have until', facts)


class EveryOtherTypeTests(LetterBase):
    def test_the_plain_letter_stops_printing_the_enum_label(self):
        note = self._note(
            'new_message', '/messages/3/',
            message='Dale Shoemaker wrote to you about the 1951 Elk.')
        letter = letters.build(note)
        self.assertEqual(
            letter['headline'],
            'Dale Shoemaker wrote to you about the 1951 Elk.')
        # The old wrapper's heading was get_notification_type_display().
        self.assertNotIn('New Message', letter['headline'])

    def test_the_headline_is_not_repeated_as_the_body(self):
        note = self._note(
            'new_message', '/messages/3/',
            message='Dale Shoemaker wrote to you. Open it to read.')
        letter = letters.build(note)
        self.assertEqual(letter['headline'], 'Dale Shoemaker wrote to you.')
        self.assertEqual(letter['lead'], 'Open it to read.')

    def test_a_one_sentence_message_gets_no_body_at_all(self):
        note = self._note('new_message', '/messages/3/',
                          message='Dale Shoemaker wrote to you.')
        self.assertEqual(letters.build(note)['lead'], '')

    def test_it_borrows_the_notification_centre_button_words(self):
        note = self._note('new_message', '/messages/3/')
        self.assertEqual(letters.build(note)['action']['label'], 'Read it')

    def test_a_link_less_notification_gets_no_button(self):
        note = self._note('new_message', '')
        self.assertIsNone(letters.build(note)['action'])

    def test_a_broken_record_still_sends_as_the_plain_letter(self):
        """These run in a cron job — one bad row must not stop the post."""
        note = self._note('auction_won', '/orders/999999/')
        letter = letters.build(note)
        self.assertTrue(letter['headline'])
        self.assertFalse(letter['can_opt_out'])


class TheSentMailTests(LetterBase):
    def test_the_subject_is_a_sentence_with_no_shouty_prefix(self):
        Bid.objects.create(
            listing=self.listing, bidder=self.buyer, amount=Decimal('390.00'))
        note = self._note('outbid', f'/listings/{self.listing.pk}/')
        self.assertTrue(send_notification_email(note))

        sent = mail.outbox[0]
        self.assertNotIn('[KeystoneBid]', sent.subject)
        self.assertIn('1921 Sullivan resident button', sent.subject)

    def test_it_goes_out_as_georgia_html_and_readable_plain_text(self):
        order = self._order()
        note = self._note('auction_won', f'/orders/{order.pk}/')
        send_notification_email(note)
        sent = mail.outbox[0]

        html = sent.alternatives[0][0]
        self.assertIn('Georgia', html)
        self.assertIn('#26331f', html)
        # This letter carries its own sign-off; the old "Please do not reply
        # to this email" is gone from every letter.
        self.assertIn('Reply and a person will answer', html)
        self.assertNotIn('do not reply', html.lower())

        # The plain part is the same letter, not the raw message string.
        self.assertIn('is yours, Ray.', sent.body)
        self.assertIn('Pay $220.40:', sent.body)
        self.assertNotIn('<', sent.body)

    def test_the_letter_is_marked_sent(self):
        note = self._note('new_message', '/messages/3/')
        send_notification_email(note)
        note.refresh_from_db()
        self.assertTrue(note.sent_email)

    def test_the_default_sign_off_replaces_do_not_reply(self):
        """The line the design says is worth stealing."""
        note = self._note('new_message', '/messages/3/')
        send_notification_email(note)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Replies to this address reach a person, not a machine', html)
        self.assertNotIn('do not reply', html.lower())


class TheCountedGapTests(LetterBase):
    """The register's counted sentence, restored with an honest denominator."""

    def _outbid_text(self):
        letter = letters.build(
            self._note('outbid', f'/listings/{self.listing.pk}/'))
        return letters.as_text(letter)

    def _hold_lycoming(self):
        from apps.collections.models import CollectionItem

        lycoming = GeographicUnit.objects.create(
            state=self.pa, name='Lycoming', unit_type='County',
            fips_code='42081', slug='pa-lycoming-letters')
        CollectionItem.objects.create(
            owner=self.buyer, title='1920 Lycoming', description='',
            state=self.pa, county=lycoming, license_year=1920,
            condition_grade='good')

    def test_the_gap_is_counted_once_the_collection_has_begun(self):
        from apps.core import ground

        GeographicUnit.objects.create(
            state=self.pa, name='Tioga', unit_type='County',
            fips_code='42117', slug='pa-tioga-letters')
        self._hold_lycoming()

        missing = ground.real_unit_count(self.pa) - 1
        self.assertGreater(missing, 1)  # otherwise the last-one line fires
        expected = (f'Sullivan is one of the {letters._word(missing)} '
                    "counties you don't have yet.")
        self.assertIn(expected, self._outbid_text())

    def test_the_one_remaining_gap_is_told_it_is_the_last(self):
        self._hold_lycoming()
        self.assertIn('Sullivan is the last county you need.',
                      self._outbid_text())

    def test_an_administrative_row_is_not_a_gap(self):
        """PA's Out-of-State code 68 is a record, not ground."""
        from decimal import Decimal

        from django.utils import timezone

        out_of_state = GeographicUnit.objects.create(
            state=self.pa, name='Out-of-State', unit_type='County',
            unit_number='68', slug='pa-oos-letters')
        pseudo = Listing.objects.create(
            seller=self.seller, title='1935 nonresident tag',
            description='d', state=self.pa, county_ref=out_of_state,
            license_year=1935, condition_grade='good',
            listing_type='auction', starting_price=Decimal('50.00'),
            current_bid=Decimal('60.00'), bid_increment=Decimal('5.00'),
            auction_end=timezone.now() + timedelta(hours=4), status='active')

        text = letters.as_text(
            letters.build(self._note('outbid', f'/listings/{pseudo.pk}/')))
        self.assertNotIn('your first', text)
        self.assertNotIn('one of the', text)
