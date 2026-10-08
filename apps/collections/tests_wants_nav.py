"""W1.12 — the Wanted list tab and the want forms land on the wants.

The Bench's "Wanted list" tab pointed at My collection's #wanted, an anchor
that never existed, and creating, editing or deleting a want dropped the
member back on the items view.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import WantedItem

WANTS = reverse('collections:my_collection') + '?view=wants'


class WantsNavTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('wn_me', password='pw')

    def setUp(self):
        self.client.force_login(self.me)

    def test_the_tab_goes_to_the_wants_and_is_marked_current_there(self):
        resp = self.client.get(WANTS)
        self.assertContains(resp, f'href="{WANTS}" class="kb-tab"\n           aria-current="page"')
        self.assertNotContains(resp, '#wanted')

    def test_removing_a_want_returns_to_the_wants(self):
        want = WantedItem.objects.create(user=self.me, notes='a 1931 Clinton')
        resp = self.client.post(reverse('collections:wanted_delete', args=[want.pk]))
        self.assertRedirects(resp, WANTS, fetch_redirect_response=False)
