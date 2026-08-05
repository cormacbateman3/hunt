"""The trade composer — turn 3a's dark table and the two rosters.

What the screen promises, the server has to keep. The right-hand roster is a
real control now, so these tests hold the line that picking from it lands on
the offer; the rosters annotate rows, so they hold that a piece at auction is
named rather than hidden; and cash runs both ways, so they hold the
direction.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.collections.models import CollectionItem, WantedItem
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing
from apps.trades import composer
from apps.trades.models import TradeOffer


class ComposerBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.walt = User.objects.create_user('cp_walt', password='pw')
        cls.rae = User.objects.create_user('cp_rae', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'is_primary_default': True})
        cls.cameron, _ = GeographicUnit.objects.get_or_create(
            state=cls.pa, name='Cameron', defaults={'slug': 'pa-cameron'})
        cls.potter, _ = GeographicUnit.objects.get_or_create(
            state=cls.pa, name='Potter', defaults={'slug': 'pa-potter'})

        for member in (cls.walt, cls.rae):
            address = Address.objects.create(
                user=member, full_name=member.username, line1='1 Main St',
                city='Williamsport', state='PA', postal_code='17701')
            member.profile.email_verified = True
            member.profile.shipping_address = address
            member.profile.save(
                update_fields=['email_verified', 'shipping_address'])

        # Rae proposes; Walt is the one being asked.
        cls.mine_a = cls._piece(cls.rae, cls.potter, 1929)
        cls.mine_b = cls._piece(cls.rae, cls.potter, 1930)
        cls.theirs_a = cls._piece(cls.walt, cls.cameron, 1916)
        cls.theirs_b = cls._piece(cls.walt, cls.cameron, 1944)

    @classmethod
    def _piece(cls, owner, county, year, **kwargs):
        return CollectionItem.objects.create(
            owner=owner, title=f'{year} {county.name}', state=cls.pa,
            county=county, license_year=year, condition_grade='good',
            is_public=True, **kwargs)

    @classmethod
    def _listing(cls, item, kind='trade', **kwargs):
        fields = {
            'seller': item.owner, 'source_collection_item': item,
            'title': item.title, 'description': 'd', 'state': cls.pa,
            'condition_grade': 'good', 'status': 'active', 'listing_type': kind,
        }
        if kind == 'auction':
            fields['starting_price'] = Decimal('40')
            fields['auction_end'] = timezone.now() + timedelta(days=3)
        else:
            fields['buy_now_price'] = Decimal('50')
        fields.update(kwargs)
        return Listing.objects.create(**fields)


class RosterTests(ComposerBase):
    def test_a_piece_at_auction_is_named_rather_than_hidden(self):
        """A collector who cannot find their own licence in their own list
        assumes the page is broken; told it is at auction, they know it
        comes back."""
        self._listing(self.mine_a, kind='auction')
        shelf = composer.roster(owner=self.rae, reader=self.rae,
                                on_table=set(), side='mine')

        row = next(r for r in shelf['rows'] if r['item'] == self.mine_a)
        self.assertFalse(row['available'])
        # A label, not the sentence. "This piece is on an auction lot right
        # now" ran off the end of a column and is the wrong voice for
        # somebody's own collection besides.
        self.assertIn('Listed in the Auction House', row['note'])

    def test_a_piece_in_the_store_stays_pickable(self):
        self._listing(self.mine_a, kind='buy_now')
        shelf = composer.roster(owner=self.rae, reader=self.rae,
                                on_table=set(), side='mine')

        row = next(r for r in shelf['rows'] if r['item'] == self.mine_a)
        self.assertTrue(row['available'])

    def test_my_shelf_says_which_pieces_they_have_asked_for(self):
        WantedItem.objects.create(user=self.rae, state=self.pa, county=self.potter,
                                  year_min=1929, year_max=1929)
        shelf = composer.roster(owner=self.rae, reader=self.rae,
                                on_table=set(), side='mine')

        row = next(r for r in shelf['rows'] if r['item'] == self.mine_a)
        self.assertEqual(row['note'], 'Matches their wants')
        # The row with something to say leads.
        self.assertEqual(shelf['rows'][0]['item'], self.mine_a)

    def test_my_shelf_marks_duplicates(self):
        dupe = self._piece(self.rae, self.potter, 1929)
        shelf = composer.roster(owner=self.rae, reader=self.rae,
                                on_table=set(), side='mine')

        row = next(r for r in shelf['rows'] if r['item'] == dupe)
        self.assertIn('Duplicate', row['note'])

    def test_their_shelf_says_what_closes_a_gap_for_me(self):
        shelf = composer.roster(owner=self.walt, reader=self.rae,
                                on_table=set(), side='theirs')

        row = next(r for r in shelf['rows'] if r['item'] == self.theirs_a)
        self.assertEqual(row['note'], 'Closes a county gap')

    def test_their_shelf_reads_tradeability_and_not_visibility(self):
        """Two separate answers. `is_public` decides whether a piece shows
        on a profile; `tradeability` decides whether its owner will hear an
        offer on it. Filtering on both hid the pieces somebody had opened to
        trade and simply not put on show — exactly the ones worth asking
        about."""
        self.theirs_a.tradeability = 'closed'
        self.theirs_a.save(update_fields=['tradeability'])
        self.theirs_b.is_public = False
        self.theirs_b.save(update_fields=['is_public'])

        shelf = composer.roster(owner=self.walt, reader=self.rae,
                                on_table=set(), side='theirs')
        self.assertEqual([r['item'] for r in shelf['rows']], [self.theirs_b])

    def test_what_is_on_the_table_leads_the_shelf(self):
        shelf = composer.roster(owner=self.rae, reader=self.rae,
                                on_table={self.mine_b.pk}, side='mine')
        self.assertEqual(shelf['rows'][0]['item'], self.mine_b)
        self.assertTrue(shelf['rows'][0]['on_table'])


class ComposerScreenTests(ComposerBase):
    def setUp(self):
        self.client.force_login(self.rae)

    def test_the_screen_draws_both_rosters_and_the_table(self):
        listing = self._listing(self.theirs_a)
        page = self.client.get(reverse('trades:propose', args=[listing.pk]))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'On the table')
        self.assertContains(page, 'I give')
        self.assertContains(page, 'I receive')
        # Both shelves, with their own posting fields.
        self.assertContains(page, 'name="offered_items"')
        self.assertContains(page, 'name="requested_items"')

    def test_the_piece_you_came_about_starts_on_the_table_and_can_come_off(self):
        """It is laid out for you, but it is an ordinary row with an ×.

        Nailing it down would refuse the commonest counter there is — the
        design's own second round is "asked for the 1944 Fulton instead".
        """
        listing = self._listing(self.theirs_a)
        page = self.client.get(reverse('trades:propose', args=[listing.pk]))

        row = next(r for r in page.context['theirs']['rows']
                   if r['item'] == self.theirs_a)
        self.assertTrue(row['on_table'])
        self.assertTrue(row['available'])
        self.assertContains(page, 'What you came for')

    def test_you_can_ask_for_something_else_instead(self):
        listing = self._listing(self.theirs_a)
        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_b.pk],   # not the one we arrived at
            'expires_days': 4,
        })
        offer = TradeOffer.objects.get()
        requested = {i.collection_item for i in offer.items.all()
                     if i.direction == 'requested'}
        self.assertEqual(requested, {self.theirs_b})
        # It still belongs to the same negotiation.
        self.assertEqual(offer.subject_item, self.theirs_a)

    def test_a_general_store_shelf_can_take_a_trade_offer(self):
        """Three ways to ask for the same licence, and this is the third."""
        listing = self._listing(self.theirs_a, kind='buy_now')
        page = self.client.get(reverse('trades:propose', args=[listing.pk]))
        self.assertEqual(page.status_code, 200)

    def test_an_auction_lot_cannot(self):
        listing = self._listing(self.theirs_a, kind='auction')
        page = self.client.get(reverse('trades:propose', args=[listing.pk]))
        self.assertEqual(page.status_code, 404)

    def test_picking_from_their_shelf_lands_on_the_offer(self):
        listing = self._listing(self.theirs_a, allow_cash=True)
        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_b.pk],
            'expires_days': 4,
        })

        offer = TradeOffer.objects.get()
        requested = {i.collection_item for i in offer.items.all()
                     if i.direction == 'requested'}
        # Only what was actually picked. The piece you arrived about is laid
        # out for you, not welded down.
        self.assertEqual(requested, {self.theirs_b})

    def test_cash_can_run_towards_the_proposer(self):
        listing = self._listing(self.theirs_a, allow_cash=True)
        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_a.pk],
            'cash_to_me': '40.00',
            'expires_days': 4,
        })

        offer = TradeOffer.objects.get()
        self.assertEqual(offer.cash_amount, Decimal('40.00'))
        self.assertEqual(offer.cash_direction, 'to_proposer')
        self.assertFalse(offer.cash_to_recipient)

    def test_asking_for_something_they_never_opened_is_refused(self):
        self.theirs_b.tradeability = 'closed'
        self.theirs_b.save(update_fields=['tradeability'])
        listing = self._listing(self.theirs_a)

        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_b.pk],
            'expires_days': 4,
        })
        self.assertFalse(TradeOffer.objects.exists())

    def test_asking_for_a_third_partys_piece_is_refused(self):
        """The hidden inputs are a suggestion; the server decides."""
        listing = self._listing(self.theirs_a)
        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.mine_b.pk],   # mine, not theirs
            'expires_days': 4,
        })
        self.assertFalse(TradeOffer.objects.exists())

    def test_a_rejected_offer_keeps_the_table_laid(self):
        """Rebuilding a five-piece trade because one field was wrong is how
        somebody stops proposing."""
        listing = self._listing(self.theirs_a)   # cash not allowed
        page = self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk, self.mine_b.pk],
            'cash_i_add': '25.00',
            'expires_days': 4,
        })

        self.assertFalse(TradeOffer.objects.exists())
        still_on = {r['item'] for r in page.context['mine']['rows'] if r['on_table']}
        self.assertEqual(still_on, {self.mine_a, self.mine_b})


class PersonLevelProposeTests(ComposerBase):
    """10.10's whole point: a trade about a piece nobody put up for sale.

    Until `TradeOffer.trade_listing` became nullable this could not exist, so
    "Propose a trade" on a collector card had to walk you to their shelf and
    hope something on it was listed.
    """

    def setUp(self):
        self.client.force_login(self.rae)

    def test_a_piece_that_was_never_listed_can_take_an_offer(self):
        self.assertFalse(self.theirs_a.listings.exists())
        page = self.client.get(
            reverse('trades:propose_on_item', args=[self.theirs_a.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['subject'], self.theirs_a)
        self.assertIsNone(page.context['listing'])

    def test_the_offer_records_the_piece_and_no_lot(self):
        self.client.post(reverse('trades:propose_on_item', args=[self.theirs_a.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_a.pk],
            'expires_days': 4,
        })
        offer = TradeOffer.objects.get()
        self.assertEqual(offer.subject_item, self.theirs_a)
        self.assertIsNone(offer.trade_listing_id)

    def test_a_closed_piece_refuses_before_the_screen_is_drawn(self):
        self.theirs_a.tradeability = 'closed'
        self.theirs_a.save(update_fields=['tradeability'])
        response = self.client.get(
            reverse('trades:propose_on_item', args=[self.theirs_a.pk]))
        self.assertRedirects(
            response, reverse('collections:item_detail', args=[self.theirs_a.pk]))

    def test_a_piece_at_auction_refuses_too(self):
        self._listing(self.theirs_a, kind='auction')
        response = self.client.get(
            reverse('trades:propose_on_item', args=[self.theirs_a.pk]))
        self.assertEqual(response.status_code, 302)

    def test_a_store_shelf_carries_its_own_cash_terms_across(self):
        """The seller said no cash on the lot; that still holds if you come
        at the piece from the collection instead."""
        self._listing(self.theirs_a, kind='buy_now', allow_cash=False)
        page = self.client.get(
            reverse('trades:propose_on_item', args=[self.theirs_a.pk]))
        self.assertFalse(page.context['allow_cash'])

    def test_a_piece_already_committed_cannot_be_asked_for_twice(self):
        self.client.post(reverse('trades:propose_on_item', args=[self.theirs_a.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_a.pk], 'expires_days': 4})
        offer = TradeOffer.objects.get()
        self.client.force_login(self.walt)
        self.client.post(reverse('trades:offer_action', args=[offer.pk, 'accept']))

        third = User.objects.create_user('cp_third', password='pw')
        address = Address.objects.create(
            user=third, full_name='third', line1='1 Main', city='W',
            state='PA', postal_code='17701')
        third.profile.email_verified = True
        third.profile.shipping_address = address
        third.profile.save(update_fields=['email_verified', 'shipping_address'])
        mine = self._piece(third, self.potter, 1955)

        from apps.trades.services import create_trade_offer
        offer, error = create_trade_offer(
            subject_item=self.theirs_a, from_user=third, to_user=self.walt,
            offered_items=[mine])
        self.assertIsNone(offer)
        self.assertIn('already committed', error)


class DecisionScreenTests(ComposerBase):
    """Turn 3a puts the shelves and the three decisions on one page.

    Answering an offer is *move a licence and send*, not *go to a second
    screen and start from nothing* — so arriving at a pending offer gets the
    same composer, with the table already laid and the sides swapped for
    whoever is reading.
    """

    def setUp(self):
        listing = self._listing(self.theirs_a, allow_cash=True)
        self.client.force_login(self.rae)
        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_b.pk],
            'cash_to_me': '40.00',
            'expires_days': 4,
        })
        self.offer = TradeOffer.objects.get()

    def _laid(self, context):
        """What is on each half of the table, from the reader's side."""
        return (
            {r['item'] for r in context['mine']['rows'] if r['on_table']},
            {r['item'] for r in context['theirs']['rows'] if r['on_table']},
        )

    def test_arriving_at_an_offer_gets_the_table_and_both_shelves(self):
        self.client.force_login(self.walt)
        page = self.client.get(reverse('trades:offer_detail', args=[self.offer.pk]))
        self.assertContains(page, 'I give')
        self.assertContains(page, 'I receive')
        self.assertContains(page, 'name="offered_items"')
        self.assertContains(page, 'name="requested_items"')

    def test_each_side_sees_their_own_half_as_theirs(self):
        self.client.force_login(self.rae)
        giving, receiving = self._laid(self.client.get(
            reverse('trades:offer_detail', args=[self.offer.pk])).context)
        self.assertEqual(giving, {self.mine_a})
        self.assertEqual(receiving, {self.theirs_b})

        self.client.force_login(self.walt)
        giving, receiving = self._laid(self.client.get(
            reverse('trades:offer_detail', args=[self.offer.pk])).context)
        self.assertEqual(giving, {self.theirs_b})
        self.assertEqual(receiving, {self.mine_a})

    def test_the_cash_arrow_turns_round_with_the_reader(self):
        """Rae asked for $40. Rae receives it; Walt pays it."""
        self.assertEqual(self.offer.cash_amount, Decimal('40.00'))
        self.assertTrue(composer.table_for(self.offer, self.rae)['cash_to_me'])
        self.assertFalse(composer.table_for(self.offer, self.walt)['cash_to_me'])

    def test_only_the_recipient_is_offered_the_three_decisions(self):
        self.client.force_login(self.walt)
        theirs = self.client.get(reverse('trades:offer_detail', args=[self.offer.pk]))
        self.assertContains(theirs, 'Review &amp; accept')
        self.assertContains(theirs, 'Decline')
        self.assertContains(theirs, 'Send counter #2')

        self.client.force_login(self.rae)
        mine = self.client.get(reverse('trades:offer_detail', args=[self.offer.pk]))
        self.assertNotContains(mine, 'Review &amp; accept')
        self.assertContains(mine, 'Withdraw')

    def test_countering_happens_in_place(self):
        """No second screen: move a licence, post the same form."""
        self.client.force_login(self.walt)
        self.client.post(reverse('trades:offer_detail', args=[self.offer.pk]), {
            'offered_items': [self.theirs_a.pk],   # drop theirs_b
            'requested_items': [self.mine_b.pk],
            'expires_days': 4,
        })

        counter = TradeOffer.objects.exclude(pk=self.offer.pk).get()
        self.assertEqual(counter.counter_to_id, self.offer.pk)
        self.assertEqual(counter.subject_item, self.offer.subject_item)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, 'countered')

    def test_the_old_counter_url_still_lands(self):
        self.client.force_login(self.walt)
        response = self.client.get(reverse('trades:counter_offer', args=[self.offer.pk]))
        self.assertRedirects(
            response, reverse('trades:offer_detail', args=[self.offer.pk]))

    def test_accepting_asks_once_before_it_commits(self):
        """Property moves in both directions at once and cannot be undone."""
        self.client.force_login(self.walt)
        page = self.client.get(reverse('trades:offer_detail', args=[self.offer.pk]))
        self.assertContains(page, 'Accept this trade?')
        self.assertContains(page, 'Leaving you')
        self.assertContains(page, 'Coming to you')

    def test_the_struck_trade_shows_the_same_table(self):
        self.client.force_login(self.walt)
        self.client.post(reverse('trades:offer_action', args=[self.offer.pk, 'accept']))

        trade = self.offer.struck_trade
        page = self.client.get(reverse('trades:trade_detail', args=[trade.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'I send')
        self.assertEqual(set(page.context['table']['giving']), {self.theirs_b})

    def test_the_recipient_can_counter_one_for_one(self):
        """The licence they asked for is your whole side of the table."""
        self.client.force_login(self.walt)
        self.client.post(reverse('trades:offer_detail', args=[self.offer.pk]), {
            'offered_items': [self.theirs_b.pk],
            'requested_items': [self.mine_b.pk],
            'expires_days': 4,
        })

        counter = TradeOffer.objects.exclude(pk=self.offer.pk).get()
        offered = {i.collection_item for i in counter.items.all()
                   if i.direction == 'offered'}
        self.assertEqual(offered, {self.theirs_b})

    def test_a_settled_offer_stops_being_a_workbench(self):
        self.client.force_login(self.walt)
        self.client.post(reverse('trades:offer_action', args=[self.offer.pk, 'decline']))

        page = self.client.get(reverse('trades:offer_detail', args=[self.offer.pk]))
        self.assertTrue(page.context['settled'])
        self.assertNotContains(page, 'name="offered_items"')


class TheDrawingTests(ComposerBase):
    """Things the design frame states outright that no other test can see.

    Both faults this class exists for were invisible to a green suite and
    obvious in a browser: a piece row whose children wrapped onto three
    lines, and a table whose licences were nearly the same colour as the
    table. Tests cannot see a layout — but they can hold the handful of
    facts the layout depends on.
    """

    def setUp(self):
        listing = self._listing(self.theirs_a, allow_cash=True)
        self.client.force_login(self.rae)
        self.client.post(reverse('trades:propose', args=[listing.pk]), {
            'offered_items': [self.mine_a.pk],
            'requested_items': [self.theirs_a.pk],
            'cash_to_me': '40.00',
            'expires_days': 4,
        })
        self.offer = TradeOffer.objects.get()

    def _page(self, who):
        self.client.force_login(who)
        return self.client.get(reverse('trades:offer_detail', args=[self.offer.pk]))

    def test_the_note_is_a_line_inside_the_row_not_a_column(self):
        """As a fourth grid column it left the title ~30px and broke words
        a character at a time."""
        html = self._page(self.rae).content.decode()
        self.assertIn('tb-piece-note', html)
        self.assertNotIn('tb-note tb-note--', html)   # the old column class

    def test_a_piece_on_the_table_stays_on_its_shelf_and_says_so(self):
        """The design shows it in both places — tinted and ticked on the
        shelf, laid out on the table."""
        page = self._page(self.rae)
        row = next(r for r in page.context['mine']['rows'] if r['item'] == self.mine_a)
        self.assertTrue(row['on_table'])
        self.assertIn('on the table', row['note'])

    def test_the_shelf_counts_the_same_set_at_both_ends(self):
        """`shown` came from a trimmed list while `total` came from a query,
        which printed "1 of 0"."""
        for shelf in (self._page(self.rae).context['mine'],
                      self._page(self.rae).context['theirs']):
            self.assertLessEqual(shelf['shown'], shelf['total'])
            self.assertEqual(shelf['total'], len(shelf['rows']))

    def test_the_cash_arrow_turns_round_with_the_reader(self):
        """Rae asked for $40, so Rae receives it and Walt pays it. The
        record does not change; the sentence does."""
        self.assertIn('to me', self._page(self.rae).context['band_terms'])
        self.assertEqual(self._page(self.rae).context['cash_side'], 'to_proposer')

        walt = self._page(self.walt)
        self.assertIn('from me', walt.context['band_terms'])
        self.assertEqual(walt.context['cash_side'], 'from_proposer')

    def test_the_cash_figure_is_in_its_box_before_any_script_runs(self):
        """And in the box it means for whoever is reading: Rae asked for it,
        so Rae sees "cash to me" and Walt sees "cash I add"."""
        walt = self._page(self.walt)
        self.assertContains(walt, 'name="cash_i_add" value="40.00"')
        self.assertContains(walt, 'Cash I add')

        rae = self._page(self.rae)
        self.assertContains(rae, 'name="cash_to_me" value="40.00"')

    def test_the_band_gives_a_date_not_a_duration(self):
        """"Both ship by Mon 10 Aug" is something you can hold against a
        calendar; "within five days" asks the reader to do the arithmetic
        that decides whether they take a strike."""
        page = self._page(self.walt)
        self.assertRegex(page.context['ship_by_date'], r'^[A-Z][a-z]{2} \d{1,2} [A-Z][a-z]{2}$')
        self.assertContains(page, 'Both ship by ' + page.context['ship_by_date'])

    def test_the_trader_card_carries_initials_for_a_blank_avatar(self):
        """The design draws a 38px square with initials, not a blank disc."""
        self.assertEqual(self._page(self.walt).context['trader_trust']['initials'], 'CP')

    def test_ships_in_is_withheld_until_it_is_a_habit(self):
        """One fast parcel is not a reputation."""
        self.assertIsNone(self._page(self.walt).context['trader_trust']['ships_in'])


class StoreActionTests(ComposerBase):
    """Three buyer actions on a General Store shelf: buy it, offer money for
    it, offer a licence for it."""

    def test_a_store_shelf_offers_a_trade(self):
        listing = self._listing(self.theirs_a, kind='buy_now')
        self.client.force_login(self.rae)
        page = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertTrue(page.context['can_offer_trade'])
        self.assertContains(page, 'Offer a licence instead')

    def test_a_closed_piece_does_not(self):
        self.theirs_a.tradeability = 'closed'
        self.theirs_a.save(update_fields=['tradeability'])
        listing = self._listing(self.theirs_a, kind='buy_now')

        self.client.force_login(self.rae)
        page = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertFalse(page.context['can_offer_trade'])
        self.assertNotContains(page, 'Offer a licence instead')

    def test_the_seller_is_not_offered_a_trade_with_themselves(self):
        listing = self._listing(self.theirs_a, kind='buy_now')
        self.client.force_login(self.walt)
        page = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertFalse(page.context['can_offer_trade'])


class TermsLineTests(TestCase):
    def test_the_table_takes_the_short_reading(self):
        self.assertEqual(
            composer.terms_line(giving=3, receiving=2, cash_amount=None,
                                cash_direction='from_proposer'),
            '3 for 2')

    def test_the_band_takes_the_longer_one(self):
        """It is the sentence the buttons are answering, so it says whose."""
        self.assertEqual(
            composer.terms_line(giving=3, receiving=2, cash_amount=None,
                                cash_direction='from_proposer', mine=True),
            'My 3 for their 2')

    def test_it_never_guesses_a_pronoun(self):
        line = composer.terms_line(giving=3, receiving=2, cash_amount=None,
                                   cash_direction='from_proposer', mine=True)
        self.assertNotIn('his', line)
        self.assertNotIn('her', line)

    def test_it_says_which_way_the_money_runs(self):
        self.assertIn(
            'to me',
            composer.terms_line(giving=3, receiving=2, cash_amount=Decimal('40'),
                                cash_direction='to_proposer'))
        self.assertIn(
            'from me',
            composer.terms_line(giving=3, receiving=2, cash_amount=Decimal('40'),
                                cash_direction='from_proposer'))

    def test_an_empty_table_says_so(self):
        self.assertEqual(
            composer.terms_line(giving=0, receiving=0, cash_amount=None,
                                cash_direction='from_proposer'),
            'Nothing on the table yet')
