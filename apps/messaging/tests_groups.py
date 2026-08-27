"""Rooms — the campfire, not the forum.

Invite-only, invisible to non-members, no public discovery anywhere.
Any member adds; anyone leaves; only the opener removes. The moderation
scan reads room messages exactly like DMs.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.messaging import services
from apps.messaging.models import Conversation, ConversationMember, MessagingSettings
from apps.moderation import services as moderation_services
from apps.moderation.models import ModerationEvent


class GroupBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name):
            user = User.objects.create_user(name, password='pw')
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.walt = verified('gr_walt')
        cls.john = verified('gr_john')
        cls.dale = verified('gr_dale')
        cls.outsider = verified('gr_nosy')
        MessagingSettings.objects.create()

    def setUp(self):
        cache.clear()

    def _room(self, members=None):
        conv, status = services.start_group(
            self.walt, 'The Tioga crowd', members or [self.john])
        assert status == 'created', status
        return conv


class RoomBasicsTests(GroupBase):
    def test_a_room_opens_with_its_people(self):
        room = self._room([self.john, self.dale])
        self.assertTrue(room.is_group)
        self.assertEqual(room.members.count(), 3)
        self.assertTrue(room.is_participant(self.walt))
        self.assertTrue(room.is_participant(self.dale))

    def test_a_room_needs_a_name(self):
        _, status = services.start_group(self.walt, '   ', [self.john])
        self.assertEqual(status, 'name_required')

    def test_the_cap_is_the_admins_number(self):
        config = MessagingSettings.objects.first()
        config.group_max_members = 2
        config.save(update_fields=['group_max_members'])
        _, status = services.start_group(self.walt, 'Too many', [self.john, self.dale])
        self.assertEqual(status, 'too_many_members')

    def test_the_master_switch_holds_the_door(self):
        config = MessagingSettings.objects.first()
        config.groups_enabled = False
        config.save(update_fields=['groups_enabled'])
        _, status = services.start_group(self.walt, 'A room', [self.john])
        self.assertEqual(status, 'groups_disabled')

    def test_an_outsider_cannot_open_or_read_the_room(self):
        room = self._room()
        self.client.force_login(self.outsider)
        resp = self.client.get(
            reverse('messaging:conversation_detail', args=[room.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_rooms_never_collide_with_the_pair_rule(self):
        """Walt and John can have their 1:1 AND any number of rooms."""
        services.start_conversation(self.walt, self.john)
        self._room([self.john])
        conv2, status = services.start_group(self.walt, 'Second room', [self.john])
        self.assertEqual(status, 'created')
        self.assertEqual(Conversation.objects.filter(is_group=True).count(), 2)


class MembershipTests(GroupBase):
    def test_any_member_brings_a_friend(self):
        room = self._room([self.john])
        _, status = services.add_group_member(room, self.john, self.dale)
        self.assertEqual(status, 'added')
        self.assertTrue(room.is_participant(self.dale))

    def test_a_block_between_adder_and_added_holds(self):
        room = self._room([self.john])
        services.apply_block(self.dale, self.john)
        _, status = services.add_group_member(room, self.john, self.dale)
        self.assertEqual(status, 'blocked')

    def test_anyone_can_leave(self):
        room = self._room([self.john])
        self.assertEqual(services.leave_group(room, self.john), 'left')
        self.assertFalse(room.is_participant(self.john))

    def test_only_the_opener_removes(self):
        room = self._room([self.john, self.dale])
        self.assertEqual(
            services.remove_group_member(room, self.john, self.dale), 'not_allowed')
        self.assertEqual(
            services.remove_group_member(room, self.walt, self.dale), 'removed')
        self.assertFalse(room.is_participant(self.dale))

    def test_the_opener_cannot_be_removed(self):
        room = self._room([self.john])
        self.assertEqual(
            services.remove_group_member(room, self.walt, self.walt), 'not_allowed')


class RoomMessagesTests(GroupBase):
    def test_a_message_reaches_everyone_else(self):
        from apps.notifications.models import Notification

        room = self._room([self.john, self.dale])
        msg, status = services.send_message(room, self.walt, 'Show this Saturday?')
        self.assertEqual(status, 'sent')
        told = set(Notification.objects.filter(
            notification_type='new_message').values_list('user__username', flat=True))
        self.assertEqual(told, {'gr_john', 'gr_dale'})

    def test_a_departed_member_cannot_post(self):
        room = self._room([self.john])
        services.leave_group(room, self.john)
        _, status = services.send_message(room, self.john, 'still here?')
        self.assertEqual(status, 'not_participant')

    def test_the_watcher_reads_rooms_too(self):
        room = self._room([self.john])
        msg, _ = services.send_message(room, self.walt, "i'm 13 btw")
        with patch.object(moderation_services.providers, 'openai_moderation',
                          return_value=None), \
             patch.object(moderation_services.providers, 'claude_escalation',
                          return_value=None):
            scan = moderation_services.scan_message(msg)
        self.assertEqual(scan.status, 'flagged')
        self.assertTrue(ModerationEvent.objects.filter(
            conversation=room, severity='urgent').exists())

    def test_the_room_renders_with_its_people(self):
        room = self._room([self.john, self.dale])
        services.send_message(room, self.john, 'Found a 1921 Sullivan at the show.')
        self.client.force_login(self.walt)
        resp = self.client.get(
            reverse('messaging:conversation_detail', args=[room.pk]))
        self.assertContains(resp, 'The Tioga crowd')
        self.assertContains(resp, '3 of you')
        self.assertContains(resp, 'Write to the room')
        self.assertContains(resp, 'Found a 1921 Sullivan')
        # The add-by-name picker hangs its list off an anchor, below the
        # input — not floating over it.
        self.assertContains(resp, 'ms-picker-anchor')

    def test_the_inbox_lists_the_room_by_name(self):
        room = self._room([self.john])
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:inbox'), follow=True)
        self.assertContains(resp, 'The Tioga crowd')
        self.assertContains(resp, '2 of you')


class RoomCreationViewTests(GroupBase):
    def test_the_form_opens_a_room_and_reports_unknown_names(self):
        self.client.force_login(self.walt)
        resp = self.client.post(reverse('messaging:group_new'), {
            'name': 'Southeast crowd',
            'members': 'gr_john nobody_real',
        }, follow=True)
        room = Conversation.objects.get(is_group=True, name='Southeast crowd')
        self.assertTrue(room.is_participant(self.john))
        self.assertContains(resp, 'nobody_real')
