"""Blocking — the entry point, and the unblock that silently did nothing.

Two faults, both introduced by rendering a write as a link:

* `unblock_user_view` is POST-only, but the privacy room rendered it as an
  `<a href>` wrapped in a form pointing somewhere else entirely. Clicking
  Unblock issued a GET, hit the method guard, and bounced the member to
  their messages — which is exactly what it looked like from outside.
* The only way to block anybody was `messaging:block_user`, which takes a
  *conversation*. You had to already be mid-argument with somebody to block
  them.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.messaging.models import Block


class BlockingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('bl_me', password='pw')
        cls.them = User.objects.create_user('bl_them', password='pw')

    def setUp(self):
        self.client.force_login(self.me)

    def test_a_profile_offers_the_block(self):
        page = self.client.get(reverse('accounts:profile', args=[self.them.username]))
        self.assertContains(page, reverse('messaging:block_person', args=[self.them.pk]))

    def test_blocking_from_a_profile_works_without_a_conversation(self):
        self.client.post(reverse('messaging:block_person', args=[self.them.pk]))
        self.assertTrue(Block.objects.filter(blocker=self.me, blocked=self.them).exists())

    def test_unblocking_actually_unblocks(self):
        Block.objects.create(blocker=self.me, blocked=self.them)
        self.client.post(reverse('messaging:unblock_user', args=[self.them.pk]),
                         {'next': reverse('accounts:profile_edit')})
        self.assertFalse(Block.objects.filter(blocker=self.me, blocked=self.them).exists())

    def test_the_privacy_room_posts_rather_than_linking(self):
        """A GET here is what silently bounced people to their messages."""
        Block.objects.create(blocker=self.me, blocked=self.them)
        room = self.client.get(reverse('accounts:profile_edit'), {'room': 'privacy'})
        html = room.content.decode()

        action = reverse('messaging:unblock_user', args=[self.them.pk])
        self.assertIn(f'<form method="post" action="{action}"', html)
        self.assertNotIn(f'<a href="{action}"', html)

    def test_the_profile_offers_the_way_back_out(self):
        Block.objects.create(blocker=self.me, blocked=self.them)
        page = self.client.get(reverse('accounts:profile', args=[self.them.username]))
        self.assertTrue(page.context['viewer_has_blocked'])
        self.assertContains(page, reverse('messaging:unblock_user', args=[self.them.pk]))

    def test_nobody_blocks_themselves(self):
        self.client.post(reverse('messaging:block_person', args=[self.me.pk]))
        self.assertFalse(Block.objects.filter(blocker=self.me).exists())

    def test_a_get_never_blocks_anybody(self):
        self.client.get(reverse('messaging:block_person', args=[self.them.pk]))
        self.assertFalse(Block.objects.exists())


class SignInLandingTests(TestCase):
    """A returning member lands on the newspaper, not on a to-do list."""

    def test_signing_in_goes_to_the_home_page(self):
        User.objects.create_user('bl_lander', password='pw-for-testing')
        response = self.client.post(reverse('accounts:login'), {
            'username': 'bl_lander', 'password': 'pw-for-testing'})
        self.assertRedirects(response, '/')
