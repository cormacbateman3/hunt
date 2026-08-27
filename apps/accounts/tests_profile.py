"""The collector profile — a display case with a person attached.

Turn 3b. The line the whole screen exists for is the one in the "looking
for" rail: *you have one, 1931, mint*. That is the difference between a
profile you read and a profile you act on, so it gets tested hardest.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Follow
from apps.collections.models import CollectionItem, WantedItem
from apps.core.models import GeographicUnit, State


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True, 'issuance_unit_label': 'County'},
        )
        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='pf-cameron')
        cls.fulton = GeographicUnit.objects.create(
            state=cls.pa, name='Fulton', slug='pf-fulton')
        cls.lycoming = GeographicUnit.objects.create(
            state=cls.pa, name='Lycoming', slug='pf-lycoming')

        cls.harold = User.objects.create_user('pf_harold', password='pw')
        cls.harold.profile.display_name = 'Harold Kreider'
        cls.harold.profile.bio = 'Third-generation Lycoming hunter.'
        cls.harold.profile.home_state = cls.pa
        cls.harold.profile.home_county = cls.lycoming
        cls.harold.profile.save()

        cls.viewer = User.objects.create_user('pf_viewer', password='pw')

        for year in (1934, 1935, 1936):
            CollectionItem.objects.create(
                owner=cls.harold, title=f'{year} Cameron', state=cls.pa,
                county=cls.cameron, license_year=year, is_public=True,
                condition_grade='good')

        cls.harold_wants_cameron = WantedItem.objects.create(
            user=cls.harold, state=cls.pa, county=cls.cameron,
            year_min=1913, year_max=1937)
        cls.harold_wants_fulton = WantedItem.objects.create(
            user=cls.harold, state=cls.pa, county=cls.fulton,
            notes='Condition no object')

    def _url(self, user=None):
        return reverse('accounts:profile', args=[(user or self.harold).username])

    # ── The trade hook ───────────────────────────────────────────────────
    def test_the_rail_says_what_you_hold_against_what_they_want(self):
        CollectionItem.objects.create(
            owner=self.viewer, title='1931 Cameron', state=self.pa,
            county=self.cameron, license_year=1931, condition_grade='mint')

        self.client.force_login(self.viewer)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'You have one')
        self.assertContains(resp, '1931')
        self.assertEqual(resp.context['wanted_answerable'], 1)

    def test_wants_you_can_answer_come_first(self):
        CollectionItem.objects.create(
            owner=self.viewer, title='1920 Fulton', state=self.pa,
            county=self.fulton, license_year=1920, condition_grade='fair')

        self.client.force_login(self.viewer)
        rows = self.client.get(self._url()).context['wanted_items']
        self.assertTrue(rows[0]['you_have'])
        self.assertEqual(rows[0]['want'], self.harold_wants_fulton)

    def test_holding_nothing_they_want_makes_no_claim(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(self._url())
        self.assertEqual(resp.context['wanted_answerable'], 0)
        self.assertNotContains(resp, 'You have one')

    def test_a_stranger_is_never_told_they_hold_something(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.context['wanted_answerable'], 0)

    def test_your_own_profile_does_not_match_your_wants_against_itself(self):
        self.client.force_login(self.harold)
        resp = self.client.get(self._url())
        self.assertEqual(resp.context['wanted_answerable'], 0)

    # ── Trust and the case ───────────────────────────────────────────────
    def test_the_trust_card_counts_things_that_happened(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.context['sale_count'], 0)
        self.assertEqual(resp.context['trade_count'], 0)
        self.assertEqual(resp.context['strike_count'], 0)
        self.assertContains(resp, 'no reviews yet')

    def test_the_display_case_holds_four(self):
        CollectionItem.objects.filter(owner=self.harold).update(featured=True)
        for year in (1937, 1938):
            CollectionItem.objects.create(
                owner=self.harold, title=f'{year} Cameron', state=self.pa,
                county=self.cameron, license_year=year, is_public=True,
                featured=True, condition_grade='good')

        resp = self.client.get(self._url())
        self.assertEqual(len(resp.context['featured_items']), 4)

    def test_a_private_collection_is_not_shown_to_a_stranger(self):
        CollectionItem.objects.filter(owner=self.harold).update(is_public=False)
        resp = self.client.get(self._url())
        self.assertEqual(resp.context['collection_total'], 0)

        self.client.force_login(self.harold)
        mine = self.client.get(self._url())
        self.assertEqual(mine.context['collection_total'], 3)

    def test_ground_covered_reports_the_run(self):
        ground = self.client.get(self._url()).context['ground']
        self.assertEqual(ground['deepest'],
                         {'county': 'Cameron', 'from': 1934, 'to': 1936})
        self.assertEqual(ground['unit_label_plural'], 'Counties')

    def test_a_decade_chip_narrows_the_shelf(self):
        CollectionItem.objects.create(
            owner=self.harold, title='1952 Cameron', state=self.pa,
            county=self.cameron, license_year=1952, is_public=True,
            condition_grade='good')

        resp = self.client.get(self._url(), {'group': '1950'})
        self.assertEqual(resp.context['collection_shown'], 1)
        self.assertEqual(resp.context['collection_total'], 4)


class FollowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user('fl_a', password='pw')
        cls.b = User.objects.create_user('fl_b', password='pw')

    def _toggle(self, target):
        return self.client.post(
            reverse('accounts:follow_toggle', args=[target.username]))

    def test_follow_then_unfollow(self):
        self.client.force_login(self.a)
        self._toggle(self.b)
        self.assertTrue(Follow.objects.filter(follower=self.a, following=self.b).exists())
        self._toggle(self.b)
        self.assertFalse(Follow.objects.filter(follower=self.a, following=self.b).exists())

    def test_you_cannot_follow_yourself(self):
        self.client.force_login(self.a)
        self._toggle(self.a)
        self.assertEqual(Follow.objects.count(), 0)

    def test_following_is_not_symmetrical(self):
        self.client.force_login(self.a)
        self._toggle(self.b)
        self.assertEqual(self.b.followers.count(), 1)
        self.assertEqual(self.b.following.count(), 0)

    def test_a_get_never_changes_anything(self):
        self.client.force_login(self.a)
        self.client.get(reverse('accounts:follow_toggle', args=[self.b.username]))
        self.assertEqual(Follow.objects.count(), 0)

    def test_signing_out_hides_the_button(self):
        html = self.client.get(
            reverse('accounts:profile', args=[self.b.username])).content.decode()
        self.assertNotIn('follow/', html)

    def test_the_follower_count_shows_on_the_profile(self):
        Follow.objects.create(follower=self.a, following=self.b)
        resp = self.client.get(reverse('accounts:profile', args=[self.b.username]))
        self.assertEqual(resp.context['follower_count'], 1)
        self.assertContains(resp, '1 follower')


class OneItemToldAsOneTests(TestCase):
    """A piece with a live lot wears a tag instead of reading as a second
    thing; a sold piece is the owner's memory, not the visitor's census;
    and drafts/scheduled lots stop being invisible to their own seller."""

    @classmethod
    def setUpTestData(cls):
        from decimal import Decimal

        from apps.listings.models import Listing

        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        cls.owner = User.objects.create_user('pf_one_owner', password='pw')
        cls.visitor = User.objects.create_user('pf_one_visitor', password='pw')

        cls.kept = CollectionItem.objects.create(
            owner=cls.owner, title='1940 Kept Statewide', state=cls.pa,
            license_year=1940, is_public=True, condition_grade='good')
        cls.listed_item = CollectionItem.objects.create(
            owner=cls.owner, title='1969 Listed PA', state=cls.pa,
            license_year=1969, is_public=True, condition_grade='good')
        cls.live_lot = Listing.objects.create(
            seller=cls.owner, source_collection_item=cls.listed_item,
            title='1969 Listed PA', description='d', state=cls.pa,
            condition_grade='good', status='active', listing_type='buy_now',
            buy_now_price=Decimal('75'))
        cls.sold_item = CollectionItem.objects.create(
            owner=cls.owner, title='1964 Departed WMD', state=cls.pa,
            license_year=1964, is_public=True, condition_grade='good',
            disposition='sold')

    def _url(self):
        return reverse('accounts:profile', args=[self.owner.username])

    def test_a_live_lot_tags_the_piece_in_the_grid(self):
        self.client.force_login(self.visitor)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'pf-piece-tag">Selling now')

    def test_a_sold_piece_is_the_owners_memory_not_the_visitors(self):
        self.client.force_login(self.visitor)
        resp = self.client.get(self._url())
        self.assertNotContains(resp, '1964 Departed WMD')
        self.assertEqual(resp.context['collection_total'], 2)

        self.client.force_login(self.owner)
        resp = self.client.get(self._url())
        self.assertContains(resp, '1964 Departed WMD')
        self.assertContains(resp, 'pf-piece-tag">Sold here')

    def test_scheduled_and_drafts_surface_only_to_their_owner(self):
        from apps.listings.models import Listing

        Listing.objects.create(
            seller=self.owner, source_collection_item=self.kept,
            title='1940 Kept Statewide', description='d', state=self.pa,
            condition_grade='good', status='scheduled', listing_type='auction')

        self.client.force_login(self.owner)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'only you see these')
        self.assertContains(resp, 'finish it')

        self.client.force_login(self.visitor)
        resp = self.client.get(self._url())
        self.assertNotContains(resp, 'only you see these')
