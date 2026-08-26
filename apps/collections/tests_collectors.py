"""Collectors — people, sorted by overlap with you.

Turn 13a (browse collectors) and 13b (everything owned). The thing worth
testing hardest is the ranking: the page is worthless if a collector holding
four things off your wanted list doesn't beat one who signed up yesterday.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import CollectionItem, WantedItem
from apps.collections.tracker import ground_covered, plural_unit
from apps.core.models import GeographicUnit, LicenseType, State
from apps.listings.models import Listing


class CollectorsBaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True, 'issuance_unit_label': 'County'},
        )
        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='pa-cameron')
        cls.lycoming = GeographicUnit.objects.create(
            state=cls.pa, name='Lycoming', slug='pa-lycoming')

        cls.me = User.objects.create_user('co_me', password='pw')
        cls.walt = User.objects.create_user('co_walt', password='pw')
        cls.dale = User.objects.create_user('co_dale', password='pw')
        cls.quiet = User.objects.create_user('co_quiet', password='pw')

        # Walt holds exactly what I want, in one county.
        for year in (1931, 1932):
            cls._item(cls.walt, county=cls.cameron, year=year)
        # Dale holds far more, but nothing I asked for.
        for year in range(1950, 1960):
            cls._item(cls.dale, county=cls.lycoming, year=year)

        cls.want = WantedItem.objects.create(
            user=cls.me, state=cls.pa, county=cls.cameron,
            year_min=1930, year_max=1935,
        )

    @classmethod
    def _item(cls, owner, *, county, year, public=True, trade=True, title=None):
        return CollectionItem.objects.create(
            owner=owner, title=title or f'{year} {county.name}',
            state=cls.pa, county=county, license_year=year,
            is_public=public, tradeability='open' if trade else 'closed', condition_grade='good',
        )


class CollectorsZoneTests(CollectorsBaseTest):
    def test_the_zone_opens_on_people_not_items(self):
        """13a: 'Browse Collections browses items. Nobody wants an item from
        a stranger — they want to know who has the rest.'"""
        resp = self.client.get(reverse('collectors'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'collections/collectors.html')
        self.assertTemplateNotUsed(resp, 'collections/browse_collections.html')

    def test_the_zone_carries_four_tabs(self):
        html = self.client.get(reverse('collectors')).content.decode()
        for label in ('Collectors', 'Everything owned', 'Trade board', 'The map'):
            self.assertIn(f'>{label}</a>', html)

    def test_the_owned_tab_renders_the_item_browse(self):
        resp = self.client.get(reverse('collectors'), {'tab': 'owned'})
        self.assertTemplateUsed(resp, 'collections/browse_collections.html')

    def test_the_map_tab_draws_the_ground_map_now(self):
        """Pass 9 cleared the register row this test used to guard: the tab
        mounts the component over real county shapes instead of saying it
        isn't drawn. 16b still holds — the shapes exist, so the control may.
        """
        resp = self.client.get(reverse('collectors'), {'tab': 'map'})
        self.assertContains(resp, 'Hunt by ground')
        self.assertContains(resp, 'ground-map.js')
        self.assertContains(resp, 'counties-10m.json')
        self.assertNotContains(resp, 'isn&rsquo;t drawn yet')


class OverlapRankingTests(CollectorsBaseTest):
    def test_overlap_beats_size(self):
        self.client.force_login(self.me)
        rows = self.client.get(reverse('collectors')).context['rows']
        order = [row['user'].username for row in rows]
        self.assertLess(order.index('co_walt'), order.index('co_dale'))

    def test_overlap_counts_wants_not_items(self):
        """Walt holds two items against one want — that is 1 of your wants."""
        self.client.force_login(self.me)
        rows = self.client.get(reverse('collectors')).context['rows']
        walt = next(r for r in rows if r['user'] == self.walt)
        self.assertEqual(walt['of_your_wants'], 1)
        self.assertEqual(walt['item_count'], 2)

    def test_a_stranger_sees_the_biggest_cases_first(self):
        """No wanted list means no overlap to rank by, so the page keeps its
        shape by leading with the largest collections instead."""
        rows = self.client.get(reverse('collectors')).context['rows']
        self.assertEqual(rows[0]['user'], self.dale)
        self.assertTrue(rows[0]['big'])

    def test_you_are_never_in_your_own_collectors_list(self):
        self._item(self.me, county=self.lycoming, year=1940)
        self.client.force_login(self.me)
        rows = self.client.get(reverse('collectors')).context['rows']
        self.assertNotIn(self.me, [row['user'] for row in rows])

    def test_a_collector_with_nothing_public_is_not_listed(self):
        self._item(self.quiet, county=self.lycoming, year=1941, public=False)
        rows = self.client.get(reverse('collectors')).context['rows']
        self.assertNotIn(self.quiet, [row['user'] for row in rows])

    def test_nobody_gets_an_empty_card(self):
        """'County and size are always known even when a collector has
        written nothing about themselves.'"""
        rows = self.client.get(reverse('collectors')).context['rows']
        for row in rows:
            self.assertTrue(row['place'], f'{row["user"]} has no place line')
            self.assertGreater(row['item_count'], 0)


class CollectorCardActionTests(CollectorsBaseTest):
    def test_a_trading_collector_gets_both_actions(self):
        html = self.client.get(reverse('collectors')).content.decode()
        self.assertIn('Propose a trade', html)
        self.assertIn('See their case', html)

    def test_propose_a_trade_is_one_click_to_the_table(self):
        """It used to walk you to their shelf and hope something on it was
        listed. It goes straight to the table now — with nothing on it,
        because from a card you have not picked a licence."""
        page = self.client.get(reverse('collectors'))
        walt_row = next(r for r in page.context['rows'] if r['user'] == self.walt)
        self.assertIsNotNone(walt_row['propose_item'])
        self.assertContains(page, reverse(
            'trades:propose_to_person', args=[self.walt.username]))
        self.assertNotContains(page, '/trades/piece/')

    def test_it_opens_on_the_piece_that_answers_one_of_my_wants(self):
        wanted = CollectionItem.objects.filter(owner=self.walt).first()
        WantedItem.objects.create(
            user=self.me, state=self.pa, county=wanted.county,
            year_min=wanted.license_year, year_max=wanted.license_year)

        self.client.force_login(self.me)
        page = self.client.get(reverse('collectors'))
        walt_row = next(r for r in page.context['rows'] if r['user'] == self.walt)
        self.assertEqual(walt_row['propose_item'], wanted)

    def test_a_piece_at_auction_is_never_the_one_it_opens_on(self):
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone

        pieces = list(CollectionItem.objects.filter(owner=self.walt))
        Listing.objects.create(
            seller=self.walt, source_collection_item=pieces[0],
            title=pieces[0].title, description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='auction',
            starting_price=Decimal('40'),
            auction_end=timezone.now() + timedelta(days=3))

        page = self.client.get(reverse('collectors'))
        walt_row = next(r for r in page.context['rows'] if r['user'] == self.walt)
        self.assertNotEqual(walt_row['propose_item'], pieces[0])

    def test_a_collector_who_trades_nothing_is_not_offered_a_trade(self):
        CollectionItem.objects.all().update(tradeability='closed')
        html = self.client.get(reverse('collectors')).content.decode()
        self.assertNotIn('Propose a trade', html)
        self.assertIn('See their case', html)

    def test_the_card_counts_what_you_could_ask_about_rather_than_flagging(self):
        """Pieces are open to trade by default, so a "will trade" badge would
        sit on every card. A count varies — and it drops when a lot goes up."""
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone

        html = self.client.get(reverse('collectors')).content.decode()
        self.assertIn('2 to trade', html)   # Walt holds two
        self.assertNotIn('Will trade', html)

        piece = CollectionItem.objects.filter(owner=self.walt).first()
        Listing.objects.create(
            seller=self.walt, source_collection_item=piece, title=piece.title,
            description='d', state=self.pa, condition_grade='good',
            status='active', listing_type='auction', starting_price=Decimal('40'),
            auction_end=timezone.now() + timedelta(days=3))

        after = self.client.get(reverse('collectors')).content.decode()
        self.assertIn('1 to trade', after)


class CollectorFacetTests(CollectorsBaseTest):
    def test_will_trade_narrows_to_people_with_something_to_trade(self):
        CollectionItem.objects.filter(owner=self.dale).update(tradeability='closed')
        rows = self.client.get(
            reverse('collectors'), {'because': 'will_trade'}).context['rows']
        self.assertIn(self.walt, [row['user'] for row in rows])
        self.assertNotIn(self.dale, [row['user'] for row in rows])

    def test_i_own_something_they_want_reads_the_other_persons_list(self):
        WantedItem.objects.create(
            user=self.dale, state=self.pa, county=self.cameron,
            year_min=1930, year_max=1935)
        self._item(self.me, county=self.cameron, year=1931)

        self.client.force_login(self.me)
        rows = self.client.get(
            reverse('collectors'), {'because': 'wants_mine'}).context['rows']
        self.assertEqual([row['user'] for row in rows], [self.dale])

    def test_size_bands_count_people_not_items(self):
        facets = self.client.get(reverse('collectors')).context['facets']
        bands = {row['label']: row['count'] for row in facets['sizes']}
        self.assertEqual(bands['Under 50'], 2)     # Walt and Dale
        self.assertEqual(bands['Over 250'], 0)

    def test_era_facet_measures_against_the_other_filters(self):
        facets = self.client.get(
            reverse('collectors'), {'size': 'small'}).context['facets']
        eras = {row['label']: row['count'] for row in facets['eras']}
        self.assertEqual(eras['1930s'], 1)         # Walt
        self.assertEqual(eras['1950s+'], 1)        # Dale

    def test_filtering_by_where_they_collect(self):
        erie = GeographicUnit.objects.create(state=self.pa, name='Erie', slug='pa-erie')
        rows = self.client.get(
            reverse('collectors'), {'county_id': erie.id}).context['rows']
        self.assertEqual(rows, [])


class EverythingOwnedTests(CollectorsBaseTest):
    def test_categories_read_as_questions_not_column_names(self):
        """13b: they 'were labelled with their database names ... and now
        read as questions a person would ask'."""
        LicenseType.objects.create(
            name='Resident', category='residency', is_system_value=True)
        LicenseType.objects.create(
            name='Junior', category='holder_eligibility', is_system_value=True)

        html = self.client.get(
            reverse('collectors'), {'tab': 'owned'}).content.decode()
        self.assertIn('Who could hold it', html)
        self.assertNotIn('Holder Eligibility', html)

    def test_apply_is_gone(self):
        """'Apply is gone: the grid updates as you go.' It survives only
        inside <noscript>, where there is nothing else to submit with."""
        html = self.client.get(
            reverse('collectors'), {'tab': 'owned'}).content.decode()
        before_noscript = html.split('<noscript>')[0]
        self.assertNotIn('>Apply<', before_noscript)
        self.assertIn('<noscript>', html)

    def test_what_you_chose_shows_as_a_removable_chip(self):
        resp = self.client.get(
            reverse('collectors'), {'tab': 'owned', 'search': 'cameron'})
        chips = resp.context['applied_filters']
        self.assertEqual([chip['label'] for chip in chips], ['Search: cameron'])
        self.assertNotIn('search=cameron', chips[0]['url'])
        self.assertIn('tab=owned', chips[0]['url'])

    def test_a_chip_removes_only_its_own_value(self):
        resp = self.client.get(reverse('collectors'), {
            'tab': 'owned', 'era': ['1930s', '1950s'],
        })
        chips = {chip['label']: chip['url'] for chip in resp.context['applied_filters']}
        self.assertIn('era=1950s', chips['1930s'])
        self.assertNotIn('era=1930s', chips['1930s'])

    def test_the_card_keeps_the_owner_and_drops_the_favourite_count(self):
        html = self.client.get(
            reverse('collectors'), {'tab': 'owned'}).content.decode()
        self.assertIn('co_walt', html)
        self.assertNotIn('fav', html.split('ow-grid')[1])


class GroundCoveredTests(CollectorsBaseTest):
    def test_deepest_run_is_the_longest_unbroken_stretch_in_one_county(self):
        for year in (1913, 1914, 1915, 1920):
            self._item(self.quiet, county=self.lycoming, year=year)
        self._item(self.quiet, county=self.cameron, year=1913)

        ground = ground_covered(self.quiet)
        self.assertEqual(ground['deepest'],
                         {'county': 'Lycoming', 'from': 1913, 'to': 1915})
        self.assertEqual(ground['held'], 2)
        self.assertEqual(ground['span'], (1913, 1920))

    def test_a_single_year_is_not_a_run(self):
        self._item(self.quiet, county=self.lycoming, year=1913)
        self.assertIsNone(ground_covered(self.quiet)['deepest'])

    def test_nothing_located_measures_nothing(self):
        self.assertIsNone(ground_covered(self.quiet))

    def test_the_unit_word_survives_the_states_that_are_not_counties(self):
        self.assertEqual(plural_unit('County'), 'Counties')
        self.assertEqual(plural_unit('Parish'), 'Parishes')
        self.assertEqual(plural_unit('Borough'), 'Boroughs')
        self.assertEqual(plural_unit('Census Area'), 'Census Areas')


class WhereTheyLiveTests(CollectorsBaseTest):
    """The register debt from Pass 3: `UserProfile.county` was free text, so
    the rail could only ask where somebody *collects*. Now it can ask both."""

    def setUp(self):
        self.walt.profile.home_state = self.pa
        self.walt.profile.home_county = self.lycoming
        self.walt.profile.save()

    def test_where_they_live_reads_the_profile_not_the_shelf(self):
        """Walt lives in Lycoming and collects Cameron. Both are true and the
        rail must not confuse them."""
        live = self.client.get(reverse('collectors'), {
            'where': 'live', 'county_id': self.lycoming.id}).context['rows']
        self.assertIn(self.walt, [row['user'] for row in live])

        collect = self.client.get(reverse('collectors'), {
            'where': 'collect', 'county_id': self.lycoming.id}).context['rows']
        self.assertNotIn(self.walt, [row['user'] for row in collect])

    def test_where_they_collect_is_still_the_default(self):
        rows = self.client.get(reverse('collectors'), {
            'county_id': self.cameron.id}).context['rows']
        self.assertIn(self.walt, [row['user'] for row in rows])

    def test_the_place_line_prefers_the_profile(self):
        rows = self.client.get(reverse('collectors')).context['rows']
        walt = next(row for row in rows if row['user'] == self.walt)
        self.assertEqual(walt['place'], 'Lycoming County, PA')

    def test_a_profile_that_says_nothing_still_gets_a_place(self):
        """Nobody gets an empty card."""
        rows = self.client.get(reverse('collectors')).context['rows']
        dale = next(row for row in rows if row['user'] == self.dale)
        self.assertTrue(dale['place'])


class TradeBoardTests(CollectorsBaseTest):
    """The board is built from pieces, not listings.

    The tab used to leave the zone for /hunt/?format=trade, which asked the
    wrong question: a collector here wants to know what they could get, not
    what is for sale.
    """

    def setUp(self):
        CollectionItem.objects.filter(owner=self.walt).update(tradeability='open')
        CollectionItem.objects.filter(owner=self.dale).update(tradeability='closed')

    def test_the_tab_stays_inside_the_zone(self):
        html = self.client.get(reverse('collectors')).content.decode()
        self.assertIn('?tab=trade', html)
        self.assertNotIn('format=trade', html)

    def test_only_pieces_somebody_opened_appear(self):
        rows = self.client.get(reverse('collectors'), {'tab': 'trade'}).context['rows']
        owners = {row['owner'] for row in rows}
        self.assertIn(self.walt, owners)
        self.assertNotIn(self.dale, owners)

    def test_a_piece_at_auction_comes_off_the_board(self):
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone

        piece = CollectionItem.objects.filter(owner=self.walt).first()
        Listing.objects.create(
            seller=self.walt, source_collection_item=piece, title=piece.title,
            description='d', state=self.pa, condition_grade='good',
            status='active', listing_type='auction', starting_price=Decimal('40'),
            auction_end=timezone.now() + timedelta(days=3))

        rows = self.client.get(reverse('collectors'), {'tab': 'trade'}).context['rows']
        self.assertNotIn(piece, [row['item'] for row in rows])

    def test_a_piece_in_the_general_store_stays_on_the_board(self):
        """Three ways to ask for the same licence — buy it, offer money for
        it, offer a licence for it. Shelving it takes away none of them."""
        from decimal import Decimal
        piece = CollectionItem.objects.filter(owner=self.walt).first()
        Listing.objects.create(
            seller=self.walt, source_collection_item=piece, title=piece.title,
            description='d', state=self.pa, condition_grade='good',
            status='active', listing_type='buy_now', buy_now_price=Decimal('50'))

        rows = self.client.get(reverse('collectors'), {'tab': 'trade'}).context['rows']
        self.assertIn(piece, [row['item'] for row in rows])

    def test_what_answers_your_wanted_list_is_marked_and_leads(self):
        self.client.force_login(self.me)
        page = self.client.get(reverse('collectors'), {'tab': 'trade'}).context
        self.assertTrue(page['rows'][0]['answers_a_want'])
        self.assertEqual(page['wanted_count'], 2)

    def test_you_never_see_your_own_pieces_on_the_board(self):
        self._item(self.me, county=self.cameron, year=1933)
        CollectionItem.objects.filter(owner=self.me).update(tradeability='open')

        self.client.force_login(self.me)
        rows = self.client.get(reverse('collectors'), {'tab': 'trade'}).context['rows']
        self.assertNotIn(self.me, {row['owner'] for row in rows})

    def test_a_stranger_sees_the_board_without_a_wanted_column(self):
        page = self.client.get(reverse('collectors'), {'tab': 'trade'}).context
        self.assertEqual(page['wanted_count'], 0)
        self.assertTrue(page['rows'])


class DistanceLineTests(CollectorsBaseTest):
    def test_miles_from_you_prints_when_both_homes_have_shapes(self):
        """Pass 9: the browse line regains its distance measure, home
        county to home county over the map's own centroids."""
        lycoming = GeographicUnit.objects.create(
            state=self.pa, name='Lycoming D', unit_type='County',
            fips_code='42081', slug='pa-lycoming-distance')
        cameron = GeographicUnit.objects.create(
            state=self.pa, name='Cameron D', unit_type='County',
            fips_code='42023', slug='pa-cameron-distance')

        me = User.objects.get(username='co_me')
        me.profile.home_state = self.pa
        me.profile.home_county = lycoming
        me.profile.save()
        walt = User.objects.get(username='co_walt')
        walt.profile.home_state = self.pa
        walt.profile.home_county = cameron
        walt.profile.save()

        self.client.force_login(me)
        rows = self.client.get(reverse('collectors')).context['rows']
        by_name = {row['user'].username: row for row in rows}
        self.assertTrue(40 <= by_name['co_walt']['miles'] <= 90,
                        by_name['co_walt']['miles'])
        # Somebody who hasn't said where home is gets no number at all.
        self.assertIsNone(by_name['co_dale']['miles'])

    def test_no_distance_for_a_viewer_with_no_stated_home(self):
        self.client.force_login(User.objects.get(username='co_me'))
        rows = self.client.get(reverse('collectors')).context['rows']
        self.assertTrue(all(row['miles'] is None for row in rows))
