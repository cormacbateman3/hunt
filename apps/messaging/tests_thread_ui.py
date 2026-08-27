"""The thread, redesigned — and reporting in one place.

No inline report furniture (the vast run of exchanges is cordial); the
header menu carries the one report flow, with an optional note and
optional pointed-at messages. Context dividers keep the one-thread-per-
pair rule honest when the talk turns to a second listing.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import State
from apps.listings.models import Listing
from apps.messaging import services
from apps.messaging.models import Conversation, Message, MessageReport


class ThreadUIBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name):
            user = User.objects.create_user(name, password='pw')
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.walt = verified('ui_walt')
        cls.john = verified('ui_john')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def setUp(self):
        cache.clear()

    def _listing(self, title):
        return Listing.objects.create(
            seller=self.john, title=title, description='d', state=self.pa,
            condition_grade='good', status='active',
            listing_type='buy_now', buy_now_price=Decimal('50'))


class ContextDividerTests(ThreadUIBase):
    def test_turning_to_a_second_listing_draws_a_divider(self):
        first = self._listing('The 1931 Cameron')
        second = self._listing('The 1940 Potter')
        conv, _ = services.start_conversation(self.walt, self.john, listing=first)
        services.send_message(conv, self.walt, 'How good is this one?')
        services.start_conversation(self.walt, self.john, listing=second)
        conv.refresh_from_db()
        services.send_message(conv, self.walt, 'And what about this one?')

        self.client.force_login(self.walt)
        html = self.client.get(
            reverse('messaging:conversation_detail', args=[conv.pk])).content.decode()
        self.assertIn('About &middot; <a', html)
        self.assertIn('The 1931 Cameron', html)
        self.assertIn('The 1940 Potter', html)

    def test_one_topic_draws_one_divider(self):
        listing = self._listing('The only topic')
        conv, _ = services.start_conversation(self.walt, self.john, listing=listing)
        services.send_message(conv, self.walt, 'first')
        services.send_message(conv, self.john, 'second')
        self.client.force_login(self.walt)
        html = self.client.get(
            reverse('messaging:conversation_detail', args=[conv.pk])).content.decode()
        self.assertEqual(html.count('ms-divider--about'), 1)


class ReportFlowTests(ThreadUIBase):
    def test_no_inline_report_furniture_remains(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        services.send_message(conv, self.john, 'hello there')
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertNotContains(resp, 'ms-msg-flag')
        self.assertNotContains(resp, 'Flag</a>')
        # One report form, in the menu.
        self.assertContains(resp, 'id="ms-report-form"', count=1)
        self.assertContains(resp, 'Point at specific messages')

    def test_a_report_can_point_at_their_messages(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        theirs, _ = services.send_message(conv, self.john, 'the message in question')
        mine, _ = services.send_message(conv, self.walt, 'my own words')

        self.client.force_login(self.walt)
        resp = self.client.post(
            reverse('messaging:report_conversation', args=[conv.pk]),
            {'reason': 'harassment', 'notes': 'see the picked one',
             'message_ids': [str(theirs.pk), str(mine.pk)]},
            follow=True)

        report = MessageReport.objects.get()
        self.assertEqual(report.reason, 'harassment')
        self.assertEqual(report.notes, 'see the picked one')
        theirs.refresh_from_db(); mine.refresh_from_db()
        self.assertEqual(theirs.moderation_state, 'flagged')
        # You cannot point a report at your own words.
        self.assertEqual(mine.moderation_state, 'ok')
        self.assertContains(resp, "We'll look at it")

    def test_the_new_reasons_are_offered(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        for label in ('Fake or counterfeit item', 'Harassment or threats',
                      'Someone may be underage'):
            self.assertContains(resp, label)


class QuietWordTests(ThreadUIBase):
    def test_a_new_exchange_gets_the_word_once(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertContains(resp, 'screened for safety by machine')

        services.send_message(conv, self.walt, 'howdy')
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertNotContains(resp, 'screened for safety by machine')


class PaneTests(ThreadUIBase):
    def test_the_inbox_opens_the_freshest_thread(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        services.send_message(conv, self.john, 'newest word')
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:inbox'))
        self.assertRedirects(
            resp, reverse('messaging:conversation_detail', args=[conv.pk]))

    def test_an_empty_inbox_keeps_the_compact_empty_state(self):
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:inbox'))
        self.assertContains(resp, 'Nothing here yet')

    def test_the_thread_page_keeps_the_filter_chips(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertContains(resp, 'Unread')
        self.assertContains(resp, 'Rooms')
        self.assertContains(resp, 'data-thread-search')

    def test_the_rooms_chip_filters_to_rooms(self):
        services.start_conversation(self.walt, self.john)
        room, _ = services.start_group(self.walt, 'The chip room', [self.john])
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:inbox') + '?show=rooms')
        self.assertContains(resp, 'The chip room')
        self.assertNotContains(resp, 'ui_john</span>')


class ListSignalTests(ThreadUIBase):
    """The left pane's two glances: this one is a room, this one is new."""

    def _third_person(self):
        dale = User.objects.create_user('ui_dale', password='pw')
        profile = dale.profile
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
        return dale

    def test_an_unread_thread_gets_the_dot_and_the_weight(self):
        quiet, _ = services.start_conversation(self.walt, self.john)
        services.send_message(quiet, self.john, 'unseen word')
        # A fresher thread so the inbox opens THAT one, leaving the
        # unread row sitting in the list where the dot must show.
        dale = self._third_person()
        fresher, _ = services.start_conversation(self.walt, dale)
        services.send_message(fresher, self.walt, 'newest word')

        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:inbox'), follow=True)
        self.assertContains(resp, 'ms-thread-dot')
        self.assertContains(resp, 'ms-thread--unread')

    def test_a_read_thread_carries_no_dot(self):
        conv, _ = services.start_conversation(self.walt, self.john)
        services.send_message(conv, self.john, 'a word')
        self.client.force_login(self.walt)
        self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        resp = self.client.get(reverse('messaging:conversation_detail', args=[conv.pk]))
        self.assertNotContains(resp, 'ms-thread-dot')

    def test_a_room_row_says_room(self):
        services.start_group(self.walt, 'The tag room', [self.john])
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:inbox'), follow=True)
        self.assertContains(resp, 'ms-thread-roomtag')


class RoomFormTests(ThreadUIBase):
    def test_the_form_reads_right_and_anchors_its_picker(self):
        self.client.force_login(self.walt)
        resp = self.client.get(reverse('messaging:group_new'))
        self.assertContains(resp, 'Maryland Waterfowl Collector Crew')
        self.assertContains(resp, 'any room member can')
        self.assertContains(resp, 'ms-picker-anchor')


class PanelCssTests(ThreadUIBase):
    """The popovers regressed invisibly once: .ms-menu-panel sets
    display:flex, which beats the hidden attribute's display:none, so
    every panel sat open on load and nothing could close it. Django
    tests can't compute CSS — pin the one rule that keeps them shut."""

    def test_hidden_still_means_hidden(self):
        from pathlib import Path

        from django.conf import settings
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'pages'
               / 'messages.css').read_text(encoding='utf-8')
        self.assertIn('.ms-menu-panel[hidden]', css)


class PeopleSearchTests(ThreadUIBase):
    def test_search_finds_people_and_never_yourself(self):
        self.client.force_login(self.walt)
        payload = self.client.get(
            reverse('messaging:user_search') + '?q=ui_').json()
        names = {row['username'] for row in payload['results']}
        self.assertIn('ui_john', names)
        self.assertNotIn('ui_walt', names)

    def test_search_needs_a_login(self):
        resp = self.client.get(reverse('messaging:user_search') + '?q=ui_')
        self.assertEqual(resp.status_code, 302)
