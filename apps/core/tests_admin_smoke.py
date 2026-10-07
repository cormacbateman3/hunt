"""Every admin page renders.

The 2026-10-06 operator audit found the User and UserProfile change pages and
the moderation-event list returning 500. Nothing exercised them, so they had
been broken since the home-county change. This walks the whole admin registry,
so the next broken ModelAdmin fails a test instead of a staff member.
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.messaging.models import Conversation
from apps.moderation.models import ModerationEvent


def _admin_url(model, view, *args):
    meta = model._meta
    return reverse(f'admin:{meta.app_label}_{meta.model_name}_{view}', args=args)


class AdminSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser('smoke_admin', 'smoke@example.com', 'pw')

    def setUp(self):
        self.client.force_login(self.staff)

    def test_every_changelist_and_its_search_renders(self):
        for model, model_admin in admin.site._registry.items():
            with self.subTest(model=model._meta.label):
                url = _admin_url(model, 'changelist')
                self.assertEqual(self.client.get(url).status_code, 200)
                if model_admin.search_fields:
                    self.assertEqual(self.client.get(url, {'q': 'x'}).status_code, 200)

    def test_every_add_page_renders_or_is_refused_on_purpose(self):
        # 403 is a deliberate refusal (singletons, scan records, bids).
        for model in admin.site._registry:
            with self.subTest(model=model._meta.label):
                status = self.client.get(_admin_url(model, 'add')).status_code
                self.assertIn(status, (200, 403))

    def test_a_member_and_their_profile_can_be_opened(self):
        member = User.objects.create_user('smoke_member', 'member@example.com', 'pw')
        profile = UserProfile.objects.get(user=member)
        self.assertEqual(self.client.get(_admin_url(User, 'change', member.pk)).status_code, 200)
        self.assertEqual(
            self.client.get(_admin_url(UserProfile, 'change', profile.pk)).status_code, 200,
        )

    def test_a_finding_on_a_group_room_lists_by_the_rooms_name(self):
        room = Conversation.objects.create(
            is_group=True, name='Show swap', created_by=self.staff,
        )
        ModerationEvent.objects.create(
            conversation=room, source='classifier', severity='review',
            category='harassment', summary='score 0.91',
        )
        resp = self.client.get(_admin_url(ModerationEvent, 'changelist'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Room: Show swap')
